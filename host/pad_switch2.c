/* (hookshot) The Nintendo Switch 2 Pro Controller over USB, read by the game itself.
 *
 * Windows gives this controller no driver that a game can use: it is a HID device that reports nothing until it is told to
 * start, over a second, vendor-specific interface (bulk endpoints; Windows binds WinUSB to it by the controller's own
 * descriptors). SDL's driver for it (SDL_hidapi_switch2.c) needs libusb, which the SDL this game ships is built without, so
 * players ran a bridge program that shows the controller as an Xbox pad, without its motion sensor.
 *
 * Here: the vendor interface is opened with WinUSB, the controller is started and its calibration read (commands as the
 * community has documented them: github.com/ndeadly/switch2_controller_research, and SDL's driver), its reports are read from
 * the HID interface, and it is given to the game as an SDL virtual gamepad with a gyroscope and an accelerometer, so
 * host/pad_sdl.c plays it as any pad: the controls page, the button prompts, rumble and the Motion controls.
 *
 * The bulk interface stays open for the controller's other parts (hos_switch2_command: its NFC reader, host/nn_nfp.c).
 * Windows only, and USB only: over Bluetooth the controller speaks a pairing and a link of Nintendo's own. HOS_SWITCH2=0
 * turns this off (a bridge program can then have the controller). */
#include "hos.h"

#ifdef _WIN32
#include <windows.h>
#include <stdbool.h>
#include <wctype.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <stdio.h>
#include <string.h>
#include <winusb.h>

#define SW2_VID 0x057e
#define SW2_PID_PRO 0x2069

/* ---- SDL3's virtual joystick (SDL3.dll, loaded by host/hos_sdl.c), its ABI declared here as gpu/vk/vk_xr.cpp does -------- */
typedef struct { int type; float rate; } SdlSensorDesc;
typedef struct {
    uint32_t version;
    uint16_t type, padding, vendor_id, product_id, naxes, nbuttons, nballs, nhats, ntouchpads, nsensors, padding2[2];
    uint32_t button_mask, axis_mask;
    const char *name;
    const void *touchpads;
    const SdlSensorDesc *sensors;
    void *userdata;
    void (*Update)(void *);
    void (*SetPlayerIndex)(void *, int);
    bool (*Rumble)(void *, uint16_t, uint16_t);
    bool (*RumbleTriggers)(void *, uint16_t, uint16_t);
    bool (*SetLED)(void *, uint8_t, uint8_t, uint8_t);
    bool (*SendEffect)(void *, const void *, int);
    bool (*SetSensorsEnabled)(void *, bool);
    void (*Cleanup)(void *);
} SdlVirtualJoystickDesc;
_Static_assert(sizeof(SdlVirtualJoystickDesc) == 136, "SDL_VirtualJoystickDesc (64-bit) is 136 bytes");
enum { SDL_INIT_JOYSTICK_ = 0x200, SDL_JOYSTICK_TYPE_GAMEPAD_ = 1, SDL_SENSOR_ACCEL_ = 1, SDL_SENSOR_GYRO_ = 2 };
enum { B_SOUTH, B_EAST, B_WEST, B_NORTH, B_BACK, B_GUIDE, B_START, B_LSTICK, B_RSTICK, B_LSHOULDER, B_RSHOULDER, B_UP, B_DOWN,
       B_LEFT, B_RIGHT, B_MISC1, B_RPADDLE1, B_LPADDLE1, B_COUNT };
enum { AX_LX, AX_LY, AX_RX, AX_RY, AX_LT, AX_RT, AX_COUNT };

static struct {
    uint32_t (*WasInit)(uint32_t);
    uint32_t (*Attach)(const SdlVirtualJoystickDesc *);
    void (*Detach)(uint32_t);
    void *(*Open)(uint32_t);
    void (*Close)(void *);
    bool (*SetAxis)(void *, int, int16_t);
    bool (*SetButton)(void *, int, bool);
    bool (*SendSensor)(void *, int, uint64_t, const float *, int);
    uint32_t id;
    void *joy;
} sdl;

typedef struct { float neutral, max, min; } Axis;
static struct {
    HANDLE usb_file, hid;
    WINUSB_INTERFACE_HANDLE usb;
    UCHAR ep_out, ep_in;
    USHORT in_len, out_len;
    Axis lx, ly, rx, ry;
    float gyro_bias[3];
    volatile LONG rumble_lo, rumble_hi, rumble_new, sensors;
    SRWLOCK usb_lk;
} pad = {.usb_lk = SRWLOCK_INIT};

/* ---- finding the controller's two interfaces --------------------------------------------------------------------------- */
/* The device path of interface `mi` of the controller, by the interface class `guid`: 1 when found */
static int find_path(const GUID *guid, int mi, wchar_t *out, size_t out_n) {
    const HDEVINFO set = SetupDiGetClassDevsW(guid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (set == INVALID_HANDLE_VALUE) return 0;
    wchar_t want[48];
    swprintf(want, 48, L"vid_%04x&pid_%04x&mi_%02x", SW2_VID, SW2_PID_PRO, mi);
    int found = 0;
    SP_DEVICE_INTERFACE_DATA ifc = {.cbSize = sizeof ifc};
    for (DWORD i = 0; !found && SetupDiEnumDeviceInterfaces(set, NULL, guid, i, &ifc); i++) {
        union { SP_DEVICE_INTERFACE_DETAIL_DATA_W d; wchar_t room[600]; } detail;
        detail.d.cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
        if (!SetupDiGetDeviceInterfaceDetailW(set, &ifc, &detail.d, sizeof detail, NULL, NULL)) continue;
        wchar_t low[600];
        size_t n = 0;
        for (; detail.d.DevicePath[n] && n + 1 < 600; n++) low[n] = (wchar_t)towlower(detail.d.DevicePath[n]);
        low[n] = 0;
        if (wcsstr(low, want) && n < out_n) wcscpy(out, detail.d.DevicePath), found = 1;
    }
    SetupDiDestroyDeviceInfoList(set);
    return found;
}
/* The WinUSB interface's own class GUID: the controller's descriptors name it (DeviceInterfaceGUIDs in its registry key),
   so it is read from there, not assumed */
static int usb_guid(GUID *out) {
    const HDEVINFO set = SetupDiGetClassDevsW(NULL, L"USB", NULL, DIGCF_PRESENT | DIGCF_ALLCLASSES);
    if (set == INVALID_HANDLE_VALUE) return 0;
    wchar_t want[48];
    swprintf(want, 48, L"VID_%04X&PID_%04X&MI_01", SW2_VID, SW2_PID_PRO);
    int found = 0;
    SP_DEVINFO_DATA dev = {.cbSize = sizeof dev};
    for (DWORD i = 0; !found && SetupDiEnumDeviceInfo(set, i, &dev); i++) {
        wchar_t id[400];
        if (!SetupDiGetDeviceInstanceIdW(set, &dev, id, 400, NULL) || !wcsstr(id, want)) continue;
        const HKEY key = SetupDiOpenDevRegKey(set, &dev, DICS_FLAG_GLOBAL, 0, DIREG_DEV, KEY_READ);
        if (key == INVALID_HANDLE_VALUE) continue;
        wchar_t text[256] = L"";
        DWORD size = sizeof text - sizeof(wchar_t), type = 0;
        if (RegQueryValueExW(key, L"DeviceInterfaceGUIDs", NULL, &type, (BYTE *)text, &size) != ERROR_SUCCESS)
            size = sizeof text - sizeof(wchar_t), RegQueryValueExW(key, L"DeviceInterfaceGUID", NULL, &type, (BYTE *)text, &size);
        RegCloseKey(key);
        unsigned d[11];
        if (swscanf(text, L"{%8x-%4x-%4x-%2x%2x-%2x%2x%2x%2x%2x%2x}", &d[0], &d[1], &d[2], &d[3], &d[4], &d[5], &d[6], &d[7], &d[8],
                    &d[9], &d[10]) == 11) {
            out->Data1 = d[0], out->Data2 = (USHORT)d[1], out->Data3 = (USHORT)d[2];
            for (int k = 0; k < 8; k++) out->Data4[k] = (UCHAR)d[3 + k];
            found = 1;
        }
    }
    SetupDiDestroyDeviceInfoList(set);
    return found;
}

/* ---- the vendor interface: a command out, its answer back --------------------------------------------------------------- */
static void pad_close(void) {
    AcquireSRWLockExclusive(&pad.usb_lk);
    if (pad.usb) WinUsb_Free(pad.usb);
    if (pad.usb_file && pad.usb_file != INVALID_HANDLE_VALUE) CloseHandle(pad.usb_file);
    pad.usb = NULL, pad.usb_file = NULL;
    ReleaseSRWLockExclusive(&pad.usb_lk);
    if (pad.hid && pad.hid != INVALID_HANDLE_VALUE) CloseHandle(pad.hid);
    pad.hid = NULL;
}
/* (usb_lk held) */
static int bulk(const uint8_t *out, unsigned out_n, uint8_t *in, unsigned in_max) {
    ULONG done = 0;
    if (!pad.usb || !WinUsb_WritePipe(pad.usb, pad.ep_out, (PUCHAR)out, out_n, &done, NULL) || done != out_n) return -1;
    if (!in) return 0;
    /* (the answer to this command: it starts with the command's number and has its subcommand at 3. One left in the pipe by an
       earlier command whose answer came late is passed over: read one behind, the sticks' calibration was another block's) */
    for (int tries = 0; tries < 4; tries++) {
        done = 0;
        if (!WinUsb_ReadPipe(pad.usb, pad.ep_in, in, in_max, &done, NULL)) return -1;
        if (done >= 4 && in[0] == out[0] && in[3] == out[3]) return (int)done;
    }
    SetLastError(ERROR_SEM_TIMEOUT);
    return -1;
}
/* A command to the controller and its answer (the answer's bytes, 0 none, -1 failed): for the controller's other parts
   (host/nn_nfp.c's reader). out: the whole command, its 8-byte header first */
int hos_switch2_command(const uint8_t *out, unsigned out_n, uint8_t *in, unsigned in_max) {
    AcquireSRWLockExclusive(&pad.usb_lk);
    const int n = bulk(out, out_n, in, in_max);
    ReleaseSRWLockExclusive(&pad.usb_lk);
    return n;
}
int hos_switch2_connected(void) { return pad.usb != NULL; }

static int read_flash(uint32_t address, uint8_t block[0x40]) {
    uint8_t cmd[16] = {0x02, 0x91, 0x00, 0x01, 0x00, 0x08, 0x00, 0x00, 0x40, 0x7e, 0x00, 0x00}, reply[0x50];
    memcpy(cmd + 12, &address, 4);
    const int n = bulk(cmd, sizeof cmd, reply, sizeof reply);
    if (n < 0x50 || memcmp(reply + 12, &address, 4)) return 0;   /* (the block asked for: its address comes back at 12) */
    memcpy(block, reply + 0x10, 0x40);
    return 1;
}
static void stick_calibration(Axis *x, Axis *y, const uint8_t *d) {   /* (nine bytes: neutral, max, min, 12 bits each, x and y) */
    x->neutral = (float)(d[0] | ((d[1] & 0x0f) << 8)), y->neutral = (float)((d[1] >> 4) | (d[2] << 4));
    x->max = (float)(d[3] | ((d[4] & 0x0f) << 8)), y->max = (float)((d[4] >> 4) | (d[5] << 4));
    x->min = (float)(d[6] | ((d[7] & 0x0f) << 8)), y->min = (float)((d[7] >> 4) | (d[8] << 4));
}

static volatile LONG pad_generation;   /* (counts the controller's starts: pad_open) */

static int pad_open(void) {
    static int told_busy;
    GUID usb_class, hid_class;
    wchar_t usb_path[600], hid_path[600];
    HidD_GetHidGuid(&hid_class);
    if (!usb_guid(&usb_class) || !find_path(&usb_class, 1, usb_path, 600) || !find_path(&hid_class, 0, hid_path, 600)) return 0;
    pad.usb_file = CreateFileW(usb_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                               FILE_FLAG_OVERLAPPED, NULL);
    if (pad.usb_file == INVALID_HANDLE_VALUE || !WinUsb_Initialize(pad.usb_file, &pad.usb)) {
        if (!told_busy)
            hos_log("switch2: a Switch 2 Pro Controller is plugged in, but another program has it (error %lu): close it and the "
                    "game takes the controller (a bridge such as Switch2Connect; Steam, which takes it for Steam Input)", GetLastError());
        told_busy = 1;
        pad.usb = NULL;
        pad_close();
        return 0;
    }
    told_busy = 0;
    USB_INTERFACE_DESCRIPTOR ifd;
    pad.ep_in = pad.ep_out = 0;
    if (WinUsb_QueryInterfaceSettings(pad.usb, 0, &ifd)) {
        for (UCHAR i = 0; i < ifd.bNumEndpoints; i++) {
            WINUSB_PIPE_INFORMATION pi;
            if (!WinUsb_QueryPipe(pad.usb, 0, i, &pi) || pi.PipeType != UsbdPipeTypeBulk) continue;
            if (USB_ENDPOINT_DIRECTION_IN(pi.PipeId)) pad.ep_in = pi.PipeId;
            else pad.ep_out = pi.PipeId;
        }
    }
    if (!pad.ep_in || !pad.ep_out) {
        hos_log("switch2: the controller's command interface has no bulk endpoints");
        pad_close();
        return 0;
    }
    WinUsb_FlushPipe(pad.usb, pad.ep_in);   /* (answers nobody read, from whoever had the controller before) */
    ULONG timeout = 500;
    WinUsb_SetPipePolicy(pad.usb, pad.ep_in, PIPE_TRANSFER_TIMEOUT, sizeof timeout, &timeout);
    WinUsb_SetPipePolicy(pad.usb, pad.ep_out, PIPE_TRANSFER_TIMEOUT, sizeof timeout, &timeout);

    /* the factory calibration (the sticks', the gyroscope's rest), the player's own stick calibration over it when there is one */
    uint8_t block[0x40];
    pad.lx = pad.ly = pad.rx = pad.ry = (Axis){2048, 1500, 1500};
    memset(pad.gyro_bias, 0, sizeof pad.gyro_bias);
    AcquireSRWLockExclusive(&pad.usb_lk);
    if (read_flash(0x13040, block)) memcpy(pad.gyro_bias, block + 4, 12);
    if (read_flash(0x13080, block)) stick_calibration(&pad.lx, &pad.ly, block + 0x28);
    if (read_flash(0x130c0, block)) stick_calibration(&pad.rx, &pad.ry, block + 0x28);
    if (read_flash(0x1fc040, block) && block[0] == 0xb2 && block[1] == 0xa1) stick_calibration(&pad.lx, &pad.ly, block + 2);
    if (read_flash(0x1fc080, block) && block[0] == 0xb2 && block[1] == 0xa1) stick_calibration(&pad.rx, &pad.ry, block + 2);
    /* started: the features its reports carry (buttons, sticks, the motion sensor), rumble, the report's format, then output.
       The first player's light */
    static const uint8_t c1[] = {0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t c2[] = {0x0c, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00};
    static const uint8_t c3[] = {0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t c4[] = {0x0a, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
                                 0xff, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t c5[] = {0x0c, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00};
    static const uint8_t c6[] = {0x01, 0x91, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t c7[] = {0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00};
    static const uint8_t c8[] = {0x03, 0x91, 0x00, 0x0a, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00};
    static const uint8_t c9[] = {0x03, 0x91, 0x00, 0x0d, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
    static const uint8_t led[] = {0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    static const struct { const uint8_t *p; unsigned n; } seq[] = {{c1, sizeof c1}, {c2, sizeof c2}, {c3, sizeof c3}, {c4, sizeof c4},
        {c5, sizeof c5}, {c6, sizeof c6}, {c7, sizeof c7}, {c8, sizeof c8}, {c9, sizeof c9}, {led, sizeof led}};
    int ok = 1;
    for (size_t i = 0; i < sizeof seq / sizeof seq[0] && ok; i++) {
        /* (a command that is not answered within the pipe's half second is no failure: only one that could not be sent) */
        if (bulk(seq[i].p, seq[i].n, block, sizeof block) < 0 && GetLastError() != ERROR_SEM_TIMEOUT) ok = 0;
    }
    ReleaseSRWLockExclusive(&pad.usb_lk);
    if (!ok) {
        hos_log("switch2: the controller did not take its start-up commands (error %lu)", GetLastError());
        pad_close();
        return 0;
    }
    pad.hid = CreateFileW(hid_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, NULL);
    if (pad.hid == INVALID_HANDLE_VALUE) {
        hos_log("switch2: the controller's reports could not be opened (error %lu)", GetLastError());
        pad_close();
        return 0;
    }
    PHIDP_PREPARSED_DATA pp;
    HIDP_CAPS caps;
    pad.in_len = pad.out_len = 64;
    if (HidD_GetPreparsedData(pad.hid, &pp)) {
        if (HidP_GetCaps(pp, &caps) == HIDP_STATUS_SUCCESS) pad.in_len = caps.InputReportByteLength, pad.out_len = caps.OutputReportByteLength;
        HidD_FreePreparsedData(pp);
    }
    InterlockedIncrement(&pad_generation);
    hos_log("switch2: Switch 2 Pro Controller over USB: started (sticks calibrated at %.0f %.0f / %.0f %.0f)", pad.lx.neutral,
            pad.ly.neutral, pad.rx.neutral, pad.ry.neutral);
    return 1;
}

/* ---- the SDL virtual gamepad ---------------------------------------------------------------------------------------------- */
static bool v_rumble(void *u, uint16_t low, uint16_t high) {
    (void)u;
    InterlockedExchange(&pad.rumble_lo, low), InterlockedExchange(&pad.rumble_hi, high), InterlockedExchange(&pad.rumble_new, 1);
    return true;
}
static bool v_sensors(void *u, bool on) {
    (void)u;
    InterlockedExchange(&pad.sensors, on ? 1 : 0);
    return true;
}
static int sdl_attach(void) {
    if (sdl.joy) return 1;
    const HMODULE m = GetModuleHandleA("SDL3.dll");
    if (!m) return 0;
    if (!sdl.Attach) {
        sdl.WasInit = (uint32_t (*)(uint32_t))(void *)GetProcAddress(m, "SDL_WasInit");
        sdl.Attach = (uint32_t (*)(const SdlVirtualJoystickDesc *))(void *)GetProcAddress(m, "SDL_AttachVirtualJoystick");
        sdl.Detach = (void (*)(uint32_t))(void *)GetProcAddress(m, "SDL_DetachVirtualJoystick");
        sdl.Open = (void *(*)(uint32_t))(void *)GetProcAddress(m, "SDL_OpenJoystick");
        sdl.Close = (void (*)(void *))(void *)GetProcAddress(m, "SDL_CloseJoystick");
        sdl.SetAxis = (bool (*)(void *, int, int16_t))(void *)GetProcAddress(m, "SDL_SetJoystickVirtualAxis");
        sdl.SetButton = (bool (*)(void *, int, bool))(void *)GetProcAddress(m, "SDL_SetJoystickVirtualButton");
        sdl.SendSensor = (bool (*)(void *, int, uint64_t, const float *, int))(void *)GetProcAddress(m, "SDL_SendJoystickVirtualSensorData");
    }
    if (!sdl.WasInit || !sdl.Attach || !sdl.Open || !sdl.SetAxis || !sdl.SetButton || !sdl.SendSensor) return 0;
    if (!(sdl.WasInit(SDL_INIT_JOYSTICK_) & SDL_INIT_JOYSTICK_)) return 0;
    static const SdlSensorDesc sensors[2] = {{SDL_SENSOR_ACCEL_, 250.0f}, {SDL_SENSOR_GYRO_, 250.0f}};
    static SdlVirtualJoystickDesc d;
    memset(&d, 0, sizeof d);
    d.version = sizeof d;
    d.type = SDL_JOYSTICK_TYPE_GAMEPAD_;
    d.vendor_id = SW2_VID, d.product_id = SW2_PID_PRO;
    d.naxes = AX_COUNT, d.nbuttons = B_COUNT, d.nsensors = 2;
    d.button_mask = (1u << B_COUNT) - 1, d.axis_mask = (1u << AX_COUNT) - 1;
    d.name = "Nintendo Switch 2 Pro Controller";
    d.sensors = sensors;
    d.Rumble = v_rumble, d.SetSensorsEnabled = v_sensors;
    sdl.id = sdl.Attach(&d);
    if (!sdl.id) return 0;
    sdl.joy = sdl.Open(sdl.id);
    for (int a = AX_LT; sdl.joy && a <= AX_RT; a++) sdl.SetAxis(sdl.joy, a, -32768);   /* (a trigger let go: the axis's low end) */
    return sdl.joy != NULL;
}
static void sdl_detach(void) {
    if (sdl.joy && sdl.Close) sdl.Close(sdl.joy);
    if (sdl.id && sdl.Detach) sdl.Detach(sdl.id);
    sdl.joy = NULL, sdl.id = 0;
}

static int16_t axis_of(const Axis *a, float raw, int invert) {
    float v = raw - a->neutral;
    v = v < 0 ? v / (a->min > 1 ? a->min : 1500.0f) : v / (a->max > 1 ? a->max : 1500.0f);
    int n = (int)(v * 32767.0f);
    n = n > 32767 ? 32767 : n < -32767 ? -32767 : n;
    return (int16_t)(invert ? -n : n);
}

/* One input report (d[0] its ID): the buttons at 5 to 8, the sticks at 11 (12 bits an axis), the motion sensor at 0x2b */
static void report(const uint8_t *d, int n) {
    static int told;
    if (!told) told = 1, hos_log("switch2: its reports arrive (ID %02x, %d bytes)", d[0], n);
    if (n >= 0x33) {   /* (HOS_SWITCH2_RUMBLE_TEST=1, a test's: a second at rest, a second of rumble, and how much the
                          controller's own accelerometer moved in each, in the log) */
        static int test = -1, last;
        static int64_t t0;
        static double rest, shaken;
        if (test < 0) test = getenv("HOS_SWITCH2_RUMBLE_TEST") && atoi(getenv("HOS_SWITCH2_RUMBLE_TEST")) ? 1 : 0;
        if (test > 0) {
            const int x = (int16_t)(d[0x31] | (d[0x32] << 8));
            const int64_t now = hos_now_ns();
            if (!t0) t0 = now, last = x;
            const double dt = (double)(now - t0) / 1e9;
            const int move = x > last ? x - last : last - x;
            last = x;
            if (dt >= 1.0 && dt < 2.0) rest += move;
            if (dt >= 2.0 && test == 1) test = 2, v_rumble(NULL, 0x8000, 0x8000);
            if (dt >= 2.2 && dt < 3.0) shaken += move;
            if (dt >= 3.0 && test == 2) {
                test = 0, v_rumble(NULL, 0, 0);
                hos_log("switch2: rumble test: the accelerometer moved %.0f in a second at rest, %.0f in 0.8 s of rumble", rest, shaken);
            }
        }
    }
    if (n < 17 || !sdl.joy) return;
    void *j = sdl.joy;
    sdl.SetButton(j, B_WEST, d[5] & 0x01), sdl.SetButton(j, B_NORTH, d[5] & 0x02);
    sdl.SetButton(j, B_SOUTH, d[5] & 0x04), sdl.SetButton(j, B_EAST, d[5] & 0x08);
    sdl.SetButton(j, B_RSHOULDER, d[5] & 0x40);
    sdl.SetAxis(j, AX_RT, d[5] & 0x80 ? 32767 : -32768);
    sdl.SetButton(j, B_BACK, d[6] & 0x01), sdl.SetButton(j, B_START, d[6] & 0x02);
    sdl.SetButton(j, B_RSTICK, d[6] & 0x04), sdl.SetButton(j, B_LSTICK, d[6] & 0x08);
    sdl.SetButton(j, B_GUIDE, d[6] & 0x10), sdl.SetButton(j, B_MISC1, d[6] & 0x20);
    sdl.SetButton(j, B_DOWN, d[7] & 0x01), sdl.SetButton(j, B_UP, d[7] & 0x02);
    sdl.SetButton(j, B_RIGHT, d[7] & 0x04), sdl.SetButton(j, B_LEFT, d[7] & 0x08);
    sdl.SetButton(j, B_LSHOULDER, d[7] & 0x40);
    sdl.SetAxis(j, AX_LT, d[7] & 0x80 ? 32767 : -32768);
    sdl.SetButton(j, B_RPADDLE1, d[8] & 0x01), sdl.SetButton(j, B_LPADDLE1, d[8] & 0x02);
    sdl.SetAxis(j, AX_LX, axis_of(&pad.lx, (float)(d[11] | ((d[12] & 0x0f) << 8)), 0));
    sdl.SetAxis(j, AX_LY, axis_of(&pad.ly, (float)((d[12] >> 4) | (d[13] << 4)), 1));
    sdl.SetAxis(j, AX_RX, axis_of(&pad.rx, (float)(d[14] | ((d[15] & 0x0f) << 8)), 0));
    sdl.SetAxis(j, AX_RY, axis_of(&pad.ry, (float)((d[15] >> 4) | (d[16] << 4)), 1));
    if (n >= 0x3d && pad.sensors) {
        /* (the sensor's axes to SDL's gamepad axes, and its units: m/s2 at 8 g full scale, rad/s at 2000 deg/s) */
        #define S16(o) ((int16_t)(d[o] | (d[(o) + 1] << 8)))
        const float as = 9.80665f * 8.0f / 32767.0f, gs = 34.8f / 32767.0f;
        const float accel[3] = {S16(0x31) * as, S16(0x35) * as, S16(0x33) * -as};
        const float gyro[3] = {S16(0x37) * gs - pad.gyro_bias[0], S16(0x3b) * gs - pad.gyro_bias[2], S16(0x39) * -gs + pad.gyro_bias[1]};
        #undef S16
        const uint64_t t = (uint64_t)hos_now_ns();
        sdl.SendSensor(j, SDL_SENSOR_ACCEL_, t, accel, 3);
        sdl.SendSensor(j, SDL_SENSOR_GYRO_, t, gyro, 3);
    }
}

/* The rumble: output report 0x02 on the HID interface, about every 12 ms while it plays and a few times when it stops. For each
   of the two motors, a byte 0x50 + a count, then three 5-byte frames, each 40 bits low first: the low band's frequency (9
   bits), a tone bit, its amplitude (10 bits), then the same for the high band. (Laid out so by the Switch2Connect bridge's
   source, and measured here with the controller lying still, by its own accelerometer: 5 at rest, 300 to 500 while it plays.
   SDL's driver packs the fields otherwise, and that did not vibrate.) Wired, the two amplitudes of a motor are kept to 511
   together, as that bridge keeps them, for what a USB port can power.

   A controller can stop taking these reports: the write then stays pending for good (seen for a whole day, in this driver and
   in that bridge alike, until the cable was pulled and put back; what brings it on is not known). On the reports' thread that
   froze the sticks and buttons, so the rumble has a thread of its own, a write is given 40 ms and then cancelled, and after
   three in a row the rumble goes on with what such a controller still plays: command 0x0A's subcommand 0x02, one of its own
   samples (1 a low buzz of about a second, 3 a soft click, 0 silence), coarser but felt. Unplugged and back, it is tried anew */
static void play_sample(uint8_t id) {
    const uint8_t cmd[12] = {0x0a, 0x91, 0x01, 0x02, 0x00, 0x04, 0x00, 0x00, id, 0x00, 0x00, 0x00};
    uint8_t reply[64];
    AcquireSRWLockExclusive(&pad.usb_lk);
    bulk(cmd, sizeof cmd, reply, sizeof reply);
    ReleaseSRWLockExclusive(&pad.usb_lk);
}
static void rumble_frame(uint8_t *out, unsigned lf_amp, unsigned hf_amp) {
    const uint64_t v = 0x0e1ull | ((uint64_t)(lf_amp & 0x3ff) << 10) | (0x1e1ull << 20) | ((uint64_t)(hf_amp & 0x3ff) << 30);
    for (int i = 0; i < 5; i++) out[i] = (uint8_t)(v >> (8 * i));
}
static DWORD WINAPI rumble_main(LPVOID unused) {
    (void)unused;
    const HANDLE ev = CreateEventW(NULL, TRUE, FALSE, NULL);
    int64_t buzz_until = 0, click_at = 0;
    int playing = 0, stops = 0, refused = 0, stuck = 0;
    LONG generation = -1;
    uint8_t count = 0;
    for (;;) {
        Sleep(12);
        const HANDLE h = pad.hid;
        if (!pad.usb || !h || h == INVALID_HANDLE_VALUE) {
            playing = 0;
            continue;
        }
        if (generation != pad_generation) generation = pad_generation, stuck = refused = 0, playing = 0;
        const uint16_t lo = (uint16_t)pad.rumble_lo, hi = (uint16_t)pad.rumble_hi;
        if (InterlockedExchange(&pad.rumble_new, 0)) stops = 3;   /* (a change, and a stop, said a few times over) */
        if (stuck) {   /* (the controller's own samples) */
            const uint16_t level = lo > hi ? lo : hi;
            const int64_t now = hos_now_ns();
            if (!level) {
                if (playing) play_sample(0), playing = 0, buzz_until = 0;
            } else if (level >= 0x2800) {
                if (now >= buzz_until) play_sample(1), buzz_until = now + 850000000LL, playing = 1;
            } else if (now >= click_at) {
                if (playing && buzz_until) play_sample(0), buzz_until = 0;
                play_sample(3), click_at = now + 220000000LL, playing = 1;
            }
            continue;
        }
        if (!lo && !hi) {
            if (stops <= 0) continue;
            stops--;
        }
        uint8_t out[64] = {0};
        const unsigned lf = (unsigned)lo * 380 / 0xffff, hf = (unsigned)hi * 130 / 0xffff;   /* (511 together at the most) */
        out[0] = 0x02;
        for (int motor = 0; motor < 2; motor++) {
            uint8_t *m = out + 1 + motor * 16;
            m[0] = (uint8_t)(0x50 | (count & 0x0f));
            for (int f = 0; f < 3; f++) rumble_frame(m + 1 + f * 5, lf, hf);
        }
        count++;
        OVERLAPPED ov = {.hEvent = ev};
        DWORD done = 0;
        ResetEvent(ev);
        int taken = WriteFile(h, out, pad.out_len > sizeof out ? sizeof out : pad.out_len, &done, &ov) != 0;
        if (!taken && GetLastError() == ERROR_IO_PENDING) {
            taken = WaitForSingleObject(ev, 40) == WAIT_OBJECT_0;
            if (!taken) CancelIoEx(h, &ov);
            GetOverlappedResult(h, &ov, &done, TRUE);
        }
        if (taken) {
            refused = 0;
        } else if (++refused >= 3) {
            stuck = 1;
            hos_log("switch2: the controller stopped taking rumble reports: its own buzz and click samples from here on (unplug it and "
                    "plug it in again for the full rumble)");
        }
    }
    return 0;
}

static DWORD WINAPI switch2_main(LPVOID unused) {
    (void)unused;
    for (;;) {
        if (!pad_open()) {
            Sleep(2000);
            continue;
        }
        while (!sdl_attach()) Sleep(500);   /* (SDL's joysticks start on the pads' thread: host/pad_sdl.c) */
        uint8_t in[256];
        const HANDLE ev = CreateEventW(NULL, TRUE, FALSE, NULL);
        int silent = 0;
        DWORD why = 0;
        for (;;) {
            OVERLAPPED ov = {.hEvent = ev};
            DWORD got = 0;
            ResetEvent(ev);
            if (!ReadFile(pad.hid, in, pad.in_len > sizeof in ? sizeof in : pad.in_len, &got, &ov)) {
                if (GetLastError() != ERROR_IO_PENDING) {
                    why = GetLastError();
                    break;
                }
                if (WaitForSingleObject(ev, 1000) != WAIT_OBJECT_0) {
                    /* (no report for a second: a controller that is on reports all the time. Three in a row: it stopped, and
                       is started again from the beginning) */
                    CancelIoEx(pad.hid, &ov);
                    GetOverlappedResult(pad.hid, &ov, &got, TRUE);
                    if (++silent >= 3) {
                        why = ERROR_TIMEOUT;
                        break;
                    }
                    continue;
                }
                if (!GetOverlappedResult(pad.hid, &ov, &got, FALSE)) {
                    why = GetLastError();
                    break;
                }
            }
            silent = 0;
            report(in, (int)got);
        }
        CloseHandle(ev);
        hos_log(why == ERROR_TIMEOUT ? "switch2: the controller sent no reports for 3 s: started again"
                                     : "switch2: the controller was unplugged (error %lu)", why);
        sdl_detach();
        pad_close();
    }
    return 0;
}

/* Started with the pads (host/pad_sdl.c), once */
void hos_switch2_start(void) {
    static LONG started;
    const char *e = getenv("HOS_SWITCH2");
    if (e && !atoi(e)) return;
    if (!InterlockedExchange(&started, 1)) {
        CreateThread(NULL, 0, switch2_main, NULL, 0, NULL);
        CreateThread(NULL, 0, rumble_main, NULL, 0, NULL);
    }
}

#else   /* (Linux: its kernel and SDL have the controller's driver) */
void hos_switch2_start(void) {}
int hos_switch2_connected(void) { return 0; }
int hos_switch2_command(const uint8_t *out, unsigned out_n, uint8_t *in, unsigned in_max) {
    (void)out, (void)out_n, (void)in, (void)in_max;
    return -1;
}
#endif
