#!/usr/bin/env python3
"""Second-stage UWP runtime changes, pinned to WiiCompiled v0.2.31."""
import argparse
from pathlib import Path

MARK = "// RR_ENHANCED_UWP_STAGE2"
def one(s,a,b):
    if s.count(a)!=1: raise ValueError("anchor changed: "+a[:100])
    return s.replace(a,b,1)

def main_cpp(s):
    s=one(s,"#include <mmsystem.h>\n#include <dbghelp.h>","#if !defined(MKW_UWP)\n#include <mmsystem.h>\n#include <dbghelp.h>\n#endif")
    s=one(s,"#if defined(_WIN32)\nint __cdecl WindowsCrtReportHook","#if defined(_WIN32) && !defined(MKW_UWP)\nint __cdecl WindowsCrtReportHook")
    # Preserve pipe helpers on desktop only; the UWP transcript writes to a file.
    s=one(s,"#if defined(_WIN32)\n    int pipeFds[2]{-1, -1};","#if defined(MKW_UWP)\n    (void)outReadFd; (void)outWriteFd; (void)targetFd;\n    return false;\n#else\n#if defined(_WIN32)\n    int pipeFds[2]{-1, -1};")
    s=one(s,"    return true;\n}\n\n#if defined(_WIN32)\nvoid AttachParentConsoleForDiagnostics()","    return true;\n#endif\n}\n\n#if defined(_WIN32) && !defined(MKW_UWP)\nvoid AttachParentConsoleForDiagnostics()")
    s=one(s,"void InitializeProcessTranscript(int argc, char** argv) {","""void InitializeProcessTranscript(int argc, char** argv) {
#if defined(MKW_UWP)
    (void)argc; (void)argv;
    auto path = RuntimeConfigFile::ApplicationDataDirectory() / "Logs" / "uwp-console.txt";
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);
    if (!ec) {
        FILE* file = nullptr;
        if (_wfreopen_s(&file, path.c_str(), L"ab", stdout)==0) {
            std::setvbuf(stdout, nullptr, _IONBF, 0);
            _dup2(_fileno(stdout), _fileno(stderr));
            std::setvbuf(stderr, nullptr, _IONBF, 0);
            std::cout.clear(); std::cerr.clear();
            std::fputs("[runtime] UWP startup\n", stdout);
        }
    }
    return;
#else""".replace('UWP startup\n"', 'UWP startup\\n"'))
    s=one(s,"    state.stderrThread = std::thread([&state]() {\n        PumpTranscriptPipe(state, state.stderrPipeReadFd, state.savedStderrFd);\n    });\n}","    state.stderrThread = std::thread([&state]() {\n        PumpTranscriptPipe(state, state.stderrPipeReadFd, state.savedStderrFd);\n    });\n#endif\n}")
    s=one(s,"std::string FormatHostStackTrace(unsigned framesToSkip) {\n#if defined(_WIN32)","std::string FormatHostStackTrace(unsigned framesToSkip) {\n#if defined(_WIN32) && !defined(MKW_UWP)")
    s=one(s,"#if defined(_WIN32)\n        ::MessageBoxA","#if defined(_WIN32) && !defined(MKW_UWP)\n        ::MessageBoxA")
    s=one(s,"    ConfigureWindowsFatalDialogBehavior();\n    InstallSehLogger();\n    WindowsTimerResolutionGuard timerResolutionGuard;","#if !defined(MKW_UWP)\n    ConfigureWindowsFatalDialogBehavior();\n    WindowsTimerResolutionGuard timerResolutionGuard;\n#endif\n    InstallSehLogger();")
    s=one(s,"int main(int argc, char** argv) {\n    return RuntimeMain(argc, argv);\n}","#if !defined(MKW_UWP)\nint main(int argc, char** argv) {\n    return RuntimeMain(argc, argv);\n}\n#endif")
    s=one(s,"#elif defined(_WIN32)\n        static constexpr std::array<GraphicsBackendEntry, 3>","#elif defined(MKW_UWP)\n        static constexpr std::array<GraphicsBackendEntry, 2> kGraphicsBackends{{\n            {\"auto\", BACKEND_D3D12}, {\"d3d12\", BACKEND_D3D12},\n        }};\n#elif defined(_WIN32)\n        static constexpr std::array<GraphicsBackendEntry, 3>")
    return s

def memory(s):
    return one(s,"#if defined(_WIN32)\n    void* frames[32]{};","#if defined(_WIN32) && !defined(MKW_UWP)\n    void* frames[32]{};")

def cpu(s):
    return one(s,'    ::MessageBoxA(nullptr, message.data, "WiiCompiled - Unsupported Processor",\n                  MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TASKMODAL);','#if !defined(MKW_UWP)\n    ::MessageBoxA(nullptr, message.data, "WiiCompiled - Unsupported Processor",\n                  MB_OK | MB_ICONERROR | MB_SETFOREGROUND | MB_TASKMODAL);\n#endif')

ENTRY = """// SDL's UWP entry point owns CoreApplication and apartment initialization.
#include <windows.h>
#define SDL_MAIN_HANDLED
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
extern int RuntimeMain(int, char**);
static int SDLCALL RunGame(int, char**) {
    char name[] = "WiiCompiled";
    char* args[] = {name, nullptr};
    return RuntimeMain(1, args);
}
extern "C" int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    return SDL_RunApp(0, nullptr, RunGame, nullptr);
}
"""

def apply(root,check):
    staged={}
    for name,fn in {"src/main.cpp":main_cpp,"src/memory.cpp":memory,"src/host_cpu_baseline.cpp":cpu}.items():
        p=root/name;s=p.read_text(encoding="utf-8")
        if not s.startswith(MARK+"\n"): staged[p]=MARK+"\n"+fn(s)
    entry=root/"src/uwp_main.cpp"
    if entry.exists():
        if entry.read_text(encoding="utf-8")!=ENTRY: raise ValueError("Unexpected existing UWP entry")
    else: staged[entry]=ENTRY
    if not check:
        for p,s in staged.items(): p.write_text(s,encoding="utf-8",newline="\n")
    print(f"{len(staged)} files {'would be changed' if check else 'changed'}")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("runtime",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args();apply(a.runtime,a.check)
