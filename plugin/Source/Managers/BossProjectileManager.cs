using System.Collections.Generic;
using HutongGames.PlayMaker;
using UnityEngine;

namespace SilksongAgent;

public class BossProjectileManager : MonoBehaviour
{
    public static BossProjectileManager Instance { get; private set; }

    private readonly HashSet<int> _dealtDamageProjectiles = new();
    private readonly HashSet<int> _activeColliderProjectiles = new();

    private readonly Dictionary<int, (Transform damager, Collider2D collider)> _trackedCircleSlashes = new();
    private readonly Dictionary<int, (Transform heroDamager, PlayMakerFSM fsm)> _trackedCrossSlashes = new();
    private readonly List<int> _pruneBuffer = new();
    private string _lastFsmState = "";

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    public void RefreshProjectileCache()
    {
        RaycastSensor.ClearProjectiles();

        string fsmState = BossStateManager.CurrentBossFsm != null
            ? BossStateManager.CurrentBossFsm.ActiveStateName
            : "";
        bool stateChanged = fsmState != _lastFsmState;
        _lastFsmState = fsmState;

        PruneDestroyedReferences();

        if (stateChanged)
        {
            DiscoverNewProjectiles();
        }

        ProcessTrackedProjectiles();
    }

    private void PruneDestroyedReferences()
    {
        _pruneBuffer.Clear();
        foreach (var kvp in _trackedCircleSlashes)
        {
            var damager = kvp.Value.damager;
            if (damager == null || !damager.gameObject.activeInHierarchy)
                _pruneBuffer.Add(kvp.Key);
        }
        foreach (var id in _pruneBuffer)
        {
            _trackedCircleSlashes.Remove(id);
            _dealtDamageProjectiles.Remove(id);
            _activeColliderProjectiles.Remove(id);
        }

        _pruneBuffer.Clear();
        foreach (var kvp in _trackedCrossSlashes)
        {
            var heroDamager = kvp.Value.heroDamager;
            if (heroDamager == null || !heroDamager.gameObject.activeInHierarchy)
                _pruneBuffer.Add(kvp.Key);
        }
        foreach (var id in _pruneBuffer)
            _trackedCrossSlashes.Remove(id);
    }

    private void DiscoverNewProjectiles()
    {
        var allObjects = FindObjectsByType<GameObject>(FindObjectsSortMode.None);

        foreach (var obj in allObjects)
        {
            if (obj == null || !obj.activeInHierarchy) continue;

            int id = obj.GetInstanceID();

            if (obj.name.Contains("lace_circle_slash") && !_trackedCircleSlashes.ContainsKey(id))
            {
                var damager = obj.transform.Find("damager");
                if (damager == null) continue;
                _trackedCircleSlashes[id] = (damager, damager.GetComponent<Collider2D>());
            }
            else if (obj.name == "Cross Slash" && !_trackedCrossSlashes.ContainsKey(id))
            {
                var heroDamager = obj.transform.Find("hero damager");
                if (heroDamager == null) continue;
                var fsm = obj.GetComponent<PlayMakerFSM>();
                if (fsm == null) continue;
                _trackedCrossSlashes[id] = (heroDamager, fsm);
            }
        }
    }

    private void ProcessTrackedProjectiles()
    {
        foreach (var kvp in _trackedCircleSlashes)
        {
            int projectileId = kvp.Key;
            var (damager, collider) = kvp.Value;

            bool colliderEnabled = collider != null && collider.enabled;

            if (colliderEnabled)
            {
                _activeColliderProjectiles.Add(projectileId);
            }
            else if (_activeColliderProjectiles.Remove(projectileId))
            {
                _dealtDamageProjectiles.Add(projectileId);
            }

            if (_dealtDamageProjectiles.Contains(projectileId)) continue;

            RaycastSensor.AddProjectile(damager.position, Constants.LaceCircleSlashRadius);
        }

        foreach (var kvp in _trackedCrossSlashes)
        {
            var (heroDamager, fsm) = kvp.Value;
            string state = fsm.ActiveStateName;
            if (state != "Idle" && state != "Attacking") continue;

            RaycastSensor.AddProjectile(heroDamager.position, Constants.CircleSlashMultiRadius);
        }
    }

    public void ClearProjectileCache()
    {
        RaycastSensor.ClearProjectiles();
        _trackedCircleSlashes.Clear();
        _trackedCrossSlashes.Clear();
        _dealtDamageProjectiles.Clear();
        _activeColliderProjectiles.Clear();
        _lastFsmState = "";
    }
}