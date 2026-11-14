# Start Hookshot in HDR on Windows with one click, and put Windows back the way it was afterwards.
#
# Hookshot's HDR row needs Windows' own "Use HDR" switch on for the display first; with it off the game stays in SDR.
# Leaving that switch on all day dims and shifts the desktop on many displays, so this script:
#
#   1. turns "Use HDR" on for one display only (the primary one, or the one -Monitor names) and remembers how it was,
#   2. sets the HDR rows in hookshot_options.ini (HDR, HDR paper white, HDR peak brightness), and the DLSS and frame
#      generation rows when asked (a copy of the file is kept once as hookshot_options.ini.before-launch-hdr),
#   3. starts the game and waits for it to close,
#   4. turns "Use HDR" off again if it was the one that turned it on.
#
# Put it beside hookshot.exe (or pass -GameDir) and run it, or point a shortcut at:
#   powershell -ExecutionPolicy Bypass -File "<game folder>\launch-hdr.ps1" -PeakNits 1000
#
#   -List            the active displays, which is primary, and whether each offers HDR and has it on; changes nothing
#   -Monitor NAME    part of a display's name as -List shows it (default: the primary display)
#   -PeakNits N      the display's peak brightness, 400 to 4000 (default 1000, the game's own default)
#   -PaperWhite N    how bright white is, 80 to 400 (default 200)
#   -Expanded        HDR Expanded (made from the SDR picture) instead of Native (the game's own HDR)
#   -Dlaa            NVIDIA DLAA: DLSS at the full output resolution (GeForce RTX, a game built with DLSS)
#   -FrameGen N      the Frame generation row: 0 Off, 1 Auto, 2 to 8 the multiplier. On, it also turns NVIDIA Reflex
#                    and frame pacing on, and V-Sync off (see below). Left as the file has it when not given.
#   -KeepVSync       with -FrameGen, leave V-Sync as the file has it
#   -NoHdr           skip the HDR part (SDR), keep the rest
#   -NoLaunch        write the settings and stop: Windows' HDR switch is not touched and the game is not started
#
# Measured on an RTX 5090 at 3840x2160, HDR Native, DLAA, Kokiri Forest (v2.1.0-rc.3-111-gbce1476c, driver 621.01):
# with V-Sync on, DLSS Frame Generation held the game at about 60 fps at 2x, 48 at 3x and 35 at 4x; with V-Sync off
# 4x kept the game near 60 (a VRR display keeps it tear-free). Hence V-Sync off with -FrameGen.
#
# The display has to offer HDR for any of this: some monitors (the Alienware AW3225QF, for one) report none until an
# HDR mode is chosen in their own on-screen menu.
#
# Windows 11 24H2 changed the API: the older "advanced colour" switch turns on wide colour there, not HDR, and its
# query reports an HDR display as unsupported. The script asks with the 24H2 calls first and falls back to the older
# pair where they are missing (Windows 10, Windows 11 before 24H2).
[CmdletBinding()]
param(
    [string]$GameDir = $PSScriptRoot,
    [string]$Monitor = '',
    [ValidateRange(400, 4000)][int]$PeakNits = 1000,
    [ValidateRange(80, 400)][int]$PaperWhite = 200,
    [ValidateRange(0, 8)][int]$FrameGen,
    [switch]$Expanded,
    [switch]$Dlaa,
    [switch]$KeepVSync,
    [switch]$NoHdr,
    [switch]$NoLaunch,
    [switch]$List
)
$ErrorActionPreference = 'Stop'
# (the menu's rows step by 100 and by 10 nits)
$PeakNits = [int]([math]::Round($PeakNits / 100.0) * 100)
$PaperWhite = [int]([math]::Round($PaperWhite / 10.0) * 10)

# ---- Windows' "Use HDR" switch, per display (Settings > System > Display > Use HDR) ----
# DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO_2 (15) and _SET_HDR_STATE (16) are wingdi.h's of SDK 10.0.26100;
# _GET_ADVANCED_COLOR_INFO (9) and _SET_ADVANCED_COLOR_STATE (10) are the pair from before.
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class HookshotHdr {
    [StructLayout(LayoutKind.Sequential)] public struct LUID { public uint Low; public int High; }
    [StructLayout(LayoutKind.Sequential)] public struct SOURCE { public LUID adapter; public uint id; public uint modeIdx; public uint status; }
    [StructLayout(LayoutKind.Sequential)] public struct RATIONAL { public uint n; public uint d; }
    [StructLayout(LayoutKind.Sequential)] public struct TARGET {
        public LUID adapter; public uint id; public uint modeIdx; public uint tech; public uint rotation; public uint scaling;
        public RATIONAL refresh; public uint scanline; public int available; public uint status; }
    [StructLayout(LayoutKind.Sequential)] public struct PATH { public SOURCE src; public TARGET tgt; public uint flags; }
    [StructLayout(LayoutKind.Sequential)] public struct MODE {
        public uint infoType; public uint id; public LUID adapter;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 48)] public byte[] data; }
    [StructLayout(LayoutKind.Sequential)] public struct HEADER { public uint type; public uint size; public LUID adapter; public uint id; }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] public struct TARGET_NAME {
        public HEADER h; public uint flags; public uint tech; public ushort mfg; public ushort product; public uint connector;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string name;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string path; }
    [StructLayout(LayoutKind.Sequential)] public struct INFO2 { public HEADER h; public uint value; public uint encoding; public uint bpc; public uint mode; }
    [StructLayout(LayoutKind.Sequential)] public struct INFO1 { public HEADER h; public uint value; public uint encoding; public uint bpc; }
    [StructLayout(LayoutKind.Sequential)] public struct SET1 { public HEADER h; public uint value; }
    [DllImport("user32.dll")] static extern int GetDisplayConfigBufferSizes(uint flags, out uint nPath, out uint nMode);
    [DllImport("user32.dll")] static extern int QueryDisplayConfig(uint flags, ref uint nPath, [Out] PATH[] paths,
        ref uint nMode, [Out] MODE[] modes, IntPtr topology);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref TARGET_NAME r);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref INFO2 r);
    [DllImport("user32.dll")] static extern int DisplayConfigGetDeviceInfo(ref INFO1 r);
    [DllImport("user32.dll")] static extern int DisplayConfigSetDeviceInfo(ref SET1 r);

    public class Display { public string Name; public bool Primary; public bool Supported; public bool On; internal PATH path; }

    static bool Modern(PATH p, out INFO2 r) {
        r = new INFO2(); r.h.type = 15; r.h.size = (uint)Marshal.SizeOf(typeof(INFO2));
        r.h.adapter = p.tgt.adapter; r.h.id = p.tgt.id;
        return DisplayConfigGetDeviceInfo(ref r) == 0;
    }
    static bool Old(PATH p, out INFO1 r) {
        r = new INFO1(); r.h.type = 9; r.h.size = (uint)Marshal.SizeOf(typeof(INFO1));
        r.h.adapter = p.tgt.adapter; r.h.id = p.tgt.id;
        return DisplayConfigGetDeviceInfo(ref r) == 0;
    }
    // The active displays, in Windows' order. Primary: the one whose desktop starts at (0, 0).
    public static List<Display> All() {
        uint np, nm;
        if (GetDisplayConfigBufferSizes(2, out np, out nm) != 0) throw new Exception("GetDisplayConfigBufferSizes failed");
        var p = new PATH[np]; var m = new MODE[nm];
        if (QueryDisplayConfig(2, ref np, p, ref nm, m, IntPtr.Zero) != 0) throw new Exception("QueryDisplayConfig failed");
        var all = new List<Display>();
        for (int i = 0; i < np; i++) {
            var d = new Display(); d.path = p[i];
            var r = new TARGET_NAME(); r.h.type = 2; r.h.size = (uint)Marshal.SizeOf(typeof(TARGET_NAME));
            r.h.adapter = p[i].tgt.adapter; r.h.id = p[i].tgt.id;
            d.Name = DisplayConfigGetDeviceInfo(ref r) == 0 && !String.IsNullOrEmpty(r.name) ? r.name : "(unnamed display)";
            uint s = p[i].src.modeIdx;   // DISPLAYCONFIG_SOURCE_MODE: width, height, pixelFormat, then position x, y
            d.Primary = s < nm && m[s].infoType == 1 && BitConverter.ToInt32(m[s].data, 12) == 0 &&
                        BitConverter.ToInt32(m[s].data, 16) == 0;
            INFO2 n; INFO1 o;
            if (Modern(p[i], out n)) { d.Supported = ((n.value >> 4) & 1) != 0; d.On = n.mode == 2; }   // highDynamicRangeSupported; ..._MODE_HDR
            else if (Old(p[i], out o)) { d.Supported = (o.value & 1) != 0; d.On = (o.value & 2) != 0; }
            all.Add(d);
        }
        return all;
    }
    // The display a name picks (any part of it, whatever the case), or the primary one for an empty name
    public static Display Find(string monitor) {
        Display first = null;
        foreach (var d in All()) {
            if (first == null) first = d;
            if (String.IsNullOrEmpty(monitor) ? d.Primary : d.Name.IndexOf(monitor, StringComparison.OrdinalIgnoreCase) >= 0) return d;
        }
        if (String.IsNullOrEmpty(monitor) && first != null) return first;
        throw new Exception("No active display named like '" + monitor + "' (-List shows the names)");
    }
    public static void Set(Display d, bool on) {
        INFO2 probe;
        var r = new SET1(); r.h.size = (uint)Marshal.SizeOf(typeof(SET1));
        r.h.adapter = d.path.tgt.adapter; r.h.id = d.path.tgt.id; r.value = on ? 1u : 0u;
        r.h.type = Modern(d.path, out probe) ? 16u : 10u;
        int e = DisplayConfigSetDeviceInfo(ref r);
        if (e != 0) throw new Exception("Windows refused to switch HDR (error " + e + ")");
    }
}
'@

if ($List) {
    [HookshotHdr]::All() | ForEach-Object {
        [pscustomobject]@{ Display = $_.Name; Primary = $_.Primary; 'Offers HDR' = $_.Supported; 'HDR on' = $_.On }
    } | Format-Table -AutoSize
    return
}

$exe = Join-Path $GameDir 'hookshot.exe'
$ini = Join-Path $GameDir 'hookshot_options.ini'
if (-not (Test-Path -LiteralPath $exe)) { throw "No hookshot.exe in '$GameDir'. Put this script beside it, or pass -GameDir." }
# (the game writes its file whole when it closes, and reads a file without options_version as one from an old version)
if (-not (Test-Path -LiteralPath $ini)) { throw 'No hookshot_options.ini yet: start the game once, close it, then run this again.' }
if (Get-Process hookshot -ErrorAction SilentlyContinue) { throw 'Hookshot is running. Close it first: it writes its settings over these when it closes.' }

# The lines of an options file with the given keys set: a key the file has keeps its place, a new one goes at the end
function Set-IniKeys([string]$path, [hashtable]$keys) {
    $seen = @{}
    $out = foreach ($l in @(Get-Content -LiteralPath $path)) {
        $k = ($l -split '=', 2)[0].Trim()
        if ($keys.ContainsKey($k)) { $seen[$k] = $true; "$k=$($keys[$k])" } else { $l }
    }
    $out = @($out) + @($keys.Keys | Where-Object { -not $seen[$_] } | Sort-Object | ForEach-Object { "$_=$($keys[$_])" })
    $tmp = "$path.tmp"
    Set-Content -LiteralPath $tmp -Value $out -Encoding ascii
    Move-Item -Force -LiteralPath $tmp -Destination $path
}

# ---- 1. HDR ----
$display = $null
$turnedHdrOn = $false
if (-not $NoHdr) {
    $display = [HookshotHdr]::Find($Monitor)
    if (-not $display.Supported) {
        Write-Warning ("'$($display.Name)' offers no HDR right now, so the game runs in SDR. Check the display's own " +
                       'menu for an HDR mode, and that Settings > System > Display shows "Use HDR" for it.')
        $NoHdr = $true
    }
    elseif (-not $display.On -and -not $NoLaunch) {
        [HookshotHdr]::Set($display, $true)
        $turnedHdrOn = $true
        for ($i = 0; $i -lt 20 -and -not [HookshotHdr]::Find($display.Name).On; $i++) { Start-Sleep -Milliseconds 250 }
        Start-Sleep -Seconds 2   # (the display re-syncs before the game makes its swapchain)
        if (-not [HookshotHdr]::Find($display.Name).On) { Write-Warning 'Windows did not turn HDR on: SDR.'; $NoHdr = $true }
    }
}

try {
    # ---- 2. Settings ----
    if (-not (Test-Path -LiteralPath "$ini.before-launch-hdr")) { Copy-Item -LiteralPath $ini -Destination "$ini.before-launch-hdr" }
    $keys = @{ hdr = $(if ($NoHdr) { 0 } elseif ($Expanded) { 1 } else { 2 }) }
    if (-not $NoHdr) { $keys.hdr_paper_white = $PaperWhite; $keys.hdr_peak_brightness = $PeakNits }
    if ($Dlaa) { $keys.dlss = 2 }
    if ($PSBoundParameters.ContainsKey('FrameGen')) {
        $keys.frame_generation = $FrameGen
        if ($FrameGen) {
            $keys.frame_pacing = 1
            $keys.nvidia_reflex = 1
            if (-not $KeepVSync) { $keys.vsync = 2 }
        }
    }
    Set-IniKeys $ini $keys
    if ($NoLaunch) { Write-Host "Settings written to $ini"; return }

    # ---- 3. The game ----
    $p = Start-Process -FilePath $exe -WorkingDirectory $GameDir -PassThru
    $p.WaitForExit()
}
finally {
    # ---- 4. HDR back as it was ----
    if ($turnedHdrOn) { try { [HookshotHdr]::Set($display, $false) } catch { Write-Warning $_ } }
}
