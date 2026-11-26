#!/usr/bin/env python3
"""Rebase the runtime portion of the Aurora UWP patch on WiiCompiled v0.2.31.

The compile database is already generated: CMake-provider changes are not
needed in this lane. Preserve current input math and renderer scheduling.
"""
from pathlib import Path
import argparse
import re

def one(s,a,b):
    if s.count(a)!=1: raise ValueError("anchor changed: "+a[:100])
    return s.replace(a,b,1)
def guard(s,a,b):
    return one(s,a,b)
def aurora(s):
    for field in ("appName","userPath","cachePath","resourcesPath","pipelineCachePath"):
        old=f"    g_config.{field} = strdup(g_config.{field});"
        s=one(s,old,f"#if defined(AURORA_WINDOWS_STORE)\n    g_config.{field} = SDL_strdup(g_config.{field});\n#else\n{old}\n#endif")
    s=one(s,"  const AuroraBackend requestedBackend = config.desiredBackend;","#if defined(AURORA_WINDOWS_STORE)\n  const AuroraBackend requestedBackend = BACKEND_D3D12;\n#else\n  const AuroraBackend requestedBackend = config.desiredBackend;\n#endif")
    return s
def system(s):
    # Diagnostic hardware probing is optional; avoid registry and NT APIs in the app container.
    return '#if defined(AURORA_WINDOWS_STORE)\n#include "system_info.hpp"\nnamespace aurora { void log_system_information() {} }\n#else\n'+s+'\n#endif\n'
def gpu(s):
    s=one(s,"#if defined(WEBGPU_DAWN) && !defined(__MINGW32__)","#if defined(WEBGPU_DAWN) && !defined(__MINGW32__) && !defined(AURORA_WINDOWS_STORE)")
    s=one(s,"void serialize_pipeline_caches() noexcept {\n#if defined(WEBGPU_DAWN) && defined(_WIN32)","void serialize_pipeline_caches() noexcept {\n#if defined(WEBGPU_DAWN) && defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)")
    return s
def input_init(s):
    old='  ASSERT(SDL_Init(SDL_INIT_HAPTIC | SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD), "Failed to initialize SDL subsystems: {}",\n         SDL_GetError());'
    return one(s,old,'#if defined(AURORA_WINDOWS_STORE)\n  ASSERT(SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD), "Failed to initialize SDL subsystems: {}", SDL_GetError());\n#else\n'+old+'\n#endif')
def window(s):
    for anchor in ["WNDPROC g_prevWindowProc = nullptr;","  const uint64_t cached = g_nativeClientSize.load(std::memory_order_acquire);","  install_window_proc_hook();","  uninstall_window_proc_hook();"]:
        s=one(s,"#if defined(_WIN32)\n"+anchor,"#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)\n"+anchor)
    return s
def binding(s):
    anchor="#elif defined(SDL_PLATFORM_WIN32)\n"
    return one(s,anchor,"""#elif defined(SDL_PLATFORM_WINRT)
  auto desc = std::make_shared<wgpu::SurfaceDescriptorFromWindowsCoreWindow>();
  desc->coreWindow = SDL_GetPointerProperty(props, SDL_PROP_WINDOW_WINRT_WINDOW_POINTER, nullptr);
  return desc;
"""+anchor)
def logging(s):
    return one(s,'#if defined(_WIN32)\n    ::MessageBoxA','#if defined(_WIN32) && !defined(AURORA_WINDOWS_STORE)\n    ::MessageBoxA')
def fixed_copy(s):
    old="std::strncpy(statOut.x0_fileName, file->m_filename, 32);"
    return one(s,old,"std::memcpy(statOut.x0_fileName, file->m_filename, 32);")
TRANSFORMS={"lib/aurora.cpp":aurora,"lib/system_info.cpp":system,"lib/webgpu/gpu.cpp":gpu,
"lib/input.cpp":input_init,"lib/window.cpp":window,"lib/dawn/BackendBinding.cpp":binding,
"lib/logging.cpp":logging,"lib/card/CardGciFolder.cpp":fixed_copy,"lib/card/CardRawFile.cpp":fixed_copy}
def main():
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("--check",action="store_true");a=p.parse_args()
    staged={}
    for rel,fn in TRANSFORMS.items():
        path=a.root/rel
        src=path.read_text(encoding="utf-8")
        if src.startswith("// RR_AURORA_UWP_V0231\n"): continue
        try: staged[path]="// RR_AURORA_UWP_V0231\n"+fn(src)
        except ValueError as e: raise ValueError(f"{rel}: {e}") from e
    if not a.check:
        for path,src in staged.items(): path.write_text(src,encoding="utf-8",newline="\n")
    print(f"{len(staged)} Aurora files {'would be changed' if a.check else 'changed'}")
if __name__=="__main__": main()
