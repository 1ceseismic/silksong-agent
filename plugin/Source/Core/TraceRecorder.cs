using System;
using System.IO;
using UnityEngine;

namespace SilksongAgent;

public unsafe class TraceRecorder : MonoBehaviour
{
    public static TraceRecorder Instance { get; private set; }

    private static readonly byte[] MagicBytes = { (byte)'S', (byte)'K', (byte)'T', (byte)'R' };
    private const uint Version = 2;

    private BinaryWriter _writer;
    private FileStream _fileStream;
    private uint _tick;
    private bool _recording;
    private int _episodeCount;
    private string _traceDir;

    public bool IsRecording => _recording;

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }
        Instance = this;
        DontDestroyOnLoad(gameObject);

        _traceDir = Path.Combine(Application.dataPath, "..", "traces");
        Directory.CreateDirectory(_traceDir);
    }

    private void Update()
    {
        if (CommandLineArgs.ReplayActive) return;

        if (Input.GetKeyDown(KeyCode.F10))
        {
            if (_recording)
                StopRecording();
            else
                StartRecording();
        }
    }

    public void StartRecording()
    {
        if (_recording) return;

        _episodeCount++;
        string filename = $"trace_{Plugin.InstanceId}_{DateTime.Now:yyyyMMdd_HHmmss}_{_episodeCount}.bin";
        string path = Path.Combine(_traceDir, filename);

        _fileStream = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None, 65536);
        _writer = new BinaryWriter(_fileStream);

        _writer.Write(MagicBytes);
        _writer.Write(Version);
        _writer.Write((uint)sizeof(GameState));
        _writer.Write((uint)sizeof(HeroPrivate));

        _tick = 0;
        _recording = true;

        Plugin.Logger.LogInfo($"[TraceRecorder] Started recording: {filename}");
    }

    public void StopRecording()
    {
        if (!_recording) return;
        _recording = false;

        _writer?.Flush();
        _writer?.Dispose();
        _writer = null;
        _fileStream?.Dispose();
        _fileStream = null;

        Plugin.Logger.LogInfo($"[TraceRecorder] Stopped recording. {_tick} ticks recorded.");
    }

    public void RecordStep(GameState gameState)
    {
        if (!_recording || _writer == null) return;

        _tick++;

        try
        {
            _writer.Write(_tick);

            byte* actions = stackalloc byte[10];
            actions[0] = ActionManager.IsLeftPressed ? (byte)1 : (byte)0;
            actions[1] = ActionManager.IsRightPressed ? (byte)1 : (byte)0;
            actions[2] = ActionManager.IsUpPressed ? (byte)1 : (byte)0;
            actions[3] = ActionManager.IsDownPressed ? (byte)1 : (byte)0;
            actions[4] = ActionManager.IsJumpPressed ? (byte)1 : (byte)0;
            actions[5] = ActionManager.IsAttackPressed ? (byte)1 : (byte)0;
            actions[6] = ActionManager.IsDashPressed ? (byte)1 : (byte)0;
            actions[7] = ActionManager.IsClawlinePressed ? (byte)1 : (byte)0;
            actions[8] = ActionManager.IsSkillPressed ? (byte)1 : (byte)0;
            actions[9] = ActionManager.IsHealPressed ? (byte)1 : (byte)0;
            _fileStream.Write(new ReadOnlySpan<byte>(actions, 10));

            _fileStream.Write(new ReadOnlySpan<byte>(&gameState, sizeof(GameState)));

            HeroPrivate hp = default;
            HeroPrivateCapture.Fill(ref hp);
            _fileStream.Write(new ReadOnlySpan<byte>(&hp, sizeof(HeroPrivate)));
        }
        catch (Exception e)
        {
            Plugin.Logger.LogError($"[TraceRecorder] Write failed, stopping recording: {e.Message}");
            StopRecording();
        }
    }

    private void OnDestroy()
    {
        StopRecording();
    }
}
