using System;
using System.IO;
using UnityEngine;

namespace SilksongAgent;

public class ReplayManager : MonoBehaviour
{
    public static ReplayManager Instance { get; private set; }

    private static readonly byte[] MagicBytes = { (byte)'S', (byte)'K', (byte)'R', (byte)'P' };
    private const int AutoArmDelayTicks = 50;

    private byte[,] _actions;
    private uint _randomSeed;
    private float _fixedDeltaTime;
    private int _cursor;
    private int _heroSeenTicks;
    private bool _armed;
    private bool _loaded;
    private bool _completed;

    private static bool AnyMovementKeyHeld()
    {
        return Input.GetKey(KeyCode.LeftArrow)  || Input.GetKey(KeyCode.RightArrow)
            || Input.GetKey(KeyCode.UpArrow)    || Input.GetKey(KeyCode.DownArrow)
            || Input.GetKey(KeyCode.Z)          || Input.GetKey(KeyCode.X)
            || Input.GetKey(KeyCode.C)          || Input.GetKey(KeyCode.A)
            || Input.GetKey(KeyCode.S)          || Input.GetKey(KeyCode.F);
    }

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);

        if (!CommandLineArgs.ReplayActive) return;

        try
        {
            LoadActionFile(CommandLineArgs.ReplayPath);
            _loaded = true;
            Plugin.Logger.LogInfo(
                $"[ReplayManager] Loaded {_actions.GetLength(0)} action frames from " +
                $"{CommandLineArgs.ReplayPath} (seed={_randomSeed}, fdt={_fixedDeltaTime}). " +
                $"Press F11 to arm playback.");
        }
        catch (Exception e)
        {
            Plugin.Logger.LogError($"[ReplayManager] Failed to load replay file: {e.Message}");
            _loaded = false;
        }
    }

    private void LoadActionFile(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        using var br = new BinaryReader(fs);

        var magic = br.ReadBytes(4);
        if (magic.Length != 4 || magic[0] != MagicBytes[0] || magic[1] != MagicBytes[1] ||
            magic[2] != MagicBytes[2] || magic[3] != MagicBytes[3])
            throw new InvalidDataException($"Bad magic: expected SKRP, got {System.Text.Encoding.ASCII.GetString(magic)}");

        uint version = br.ReadUInt32();
        if (version != 1u)
            throw new InvalidDataException($"Unsupported replay version {version} (expected 1)");

        _fixedDeltaTime = br.ReadSingle();
        _randomSeed = br.ReadUInt32();
        uint count = br.ReadUInt32();

        _actions = new byte[count, 10];
        for (uint i = 0; i < count; i++)
        {
            var buf = br.ReadBytes(10);
            if (buf.Length != 10)
                throw new EndOfStreamException($"Truncated at record {i}");
            for (int k = 0; k < 10; k++) _actions[i, k] = buf[k];
        }
    }

    private void Update()
    {
        if (!CommandLineArgs.ReplayActive || !_loaded || _armed || _completed) return;

        var hero = HeroController.instance;
        bool stable = hero != null
            && hero.cState != null
            && hero.cState.onGround
            && !hero.cState.transitioning
            && !hero.cState.dashing
            && !hero.cState.jumping
            && !AnyMovementKeyHeld();
        if (stable) {
            _heroSeenTicks++;
            if (_heroSeenTicks >= AutoArmDelayTicks) {
                Arm();
                return;
            }
        } else {
            _heroSeenTicks = 0;
        }

        if (Input.GetKeyDown(KeyCode.F11)) Arm();
    }

    private void Arm()
    {
        UnityEngine.Random.InitState(unchecked((int)_randomSeed));
        if (_fixedDeltaTime > 0f) Time.fixedDeltaTime = _fixedDeltaTime;
        Time.timeScale = CommandLineArgs.TimeScale > 0f ? CommandLineArgs.TimeScale : 1.0f;

        ActionManager.ResetInputs();
        ActionManager.IsAgentControlEnabled = true;

        TraceRecorder.Instance?.StartRecording();

        _cursor = 0;
        _armed = true;
        Plugin.Logger.LogInfo(
            $"[ReplayManager] Armed: playing {_actions.GetLength(0)} frames.");
    }

    private void FixedUpdate()
    {
        if (!_armed) return;

        int n = _actions.GetLength(0);
        if (_cursor >= n)
        {
            Plugin.Logger.LogInfo("[ReplayManager] Playback complete; stopping + quitting.");
            TraceRecorder.Instance?.StopRecording();
            _armed = false;
            _completed = true;
            Application.Quit();
            return;
        }

        ActionManager.IsLeftPressed     = _actions[_cursor, 0] != 0;
        ActionManager.IsRightPressed    = _actions[_cursor, 1] != 0;
        ActionManager.IsUpPressed       = _actions[_cursor, 2] != 0;
        ActionManager.IsDownPressed     = _actions[_cursor, 3] != 0;
        ActionManager.IsJumpPressed     = _actions[_cursor, 4] != 0;
        ActionManager.IsAttackPressed   = _actions[_cursor, 5] != 0;
        ActionManager.IsDashPressed     = _actions[_cursor, 6] != 0;
        ActionManager.IsClawlinePressed = _actions[_cursor, 7] != 0;
        ActionManager.IsSkillPressed    = _actions[_cursor, 8] != 0;
        ActionManager.IsHealPressed     = _actions[_cursor, 9] != 0;

        _cursor++;

        SharedMemoryManager.Instance?.WriteGameState();
    }
}
