from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window
import datetime
import json
import os

# Fully compatible mobile hardware layers
from plyer import flash, vibrator, gps, tts, battery

try:
    from jnius import autoclass
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    Settings = autoclass('android.provider.Settings')
    Build = autoclass('android.os.Build')
    BuildVersion = autoclass('android.os.Build$VERSION')
except ImportError:
    PythonActivity = Intent = Settings = Build = BuildVersion = None

# Configuration Definitions
CONFIG_FILE = "config.json"
MAX_LOGS = 500

DEFAULT_CONFIG = {
    "boot_speed": 0.04,
    "haptic_enabled": True,
    "sound_enabled": True,
    "current_theme": "Orange",
    "stats": {
        "wifi": 0, "ble": 0, "voice": 0, "haptic": 0, "gps": 0, "strobe": 0
    }
}

APP_CONFIG = {}


def load_application_config():
    """Loads system parameters securely from persistent JSON storage while validating keys"""
    global APP_CONFIG
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                APP_CONFIG = json.load(f)
        except Exception:
            APP_CONFIG = DEFAULT_CONFIG.copy()
    else:
        APP_CONFIG = DEFAULT_CONFIG.copy()

    for key, value in DEFAULT_CONFIG.items():
        if key not in APP_CONFIG:
            APP_CONFIG[key] = value

    if not isinstance(APP_CONFIG.get("stats"), dict):
        APP_CONFIG["stats"] = DEFAULT_CONFIG["stats"].copy()
    else:
        for skey, sval in DEFAULT_CONFIG["stats"].items():
            if skey not in APP_CONFIG["stats"]:
                APP_CONFIG["stats"][skey] = sval


def save_application_config():
    """Flushes active config variables down into physical flash memory storage"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(APP_CONFIG, f, indent=4)
    except Exception:
        pass


THEME_PALETTE = {
    "Orange":       {"bg": (1.0, 0.35, 0.0, 1.0), "txt": (0.08, 0.09, 0.12, 1.0)},
    "Stealth":      {"bg": (0.05, 0.05, 0.07, 1.0), "txt": (0.5, 0.5, 0.55, 1.0)},
    "Matrix Green": {"bg": (0.0, 0.02, 0.0, 1.0),    "txt": (0.0, 1.0, 0.0, 1.0)},
    "Ice Blue":     {"bg": (0.0, 0.1, 0.2, 1.0),    "txt": (0.3, 0.8, 1.0, 1.0)},
    "Purple Neon":  {"bg": (0.1, 0.0, 0.15, 1.0),   "txt": (0.9, 0.4, 1.0, 1.0)},
    "Red Alert":    {"bg": (0.2, 0.0, 0.0, 1.0),    "txt": (1.0, 0.2, 0.2, 1.0)}
}


class TerminalScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=6)
        self.master_log_history = []
        
        self.status_bar = Label(
            text="🟡 BOOTING SYSTEM KERNEL...", font_name="Courier", font_size="13sp",
            bold=True, color=(1, 0.75, 0, 1), size_hint_y=0.06
        )
        self.layout.add_widget(self.status_bar)
        
        self.screen_bg = BoxLayout(padding=8, size_hint_y=0.3)
        with self.screen_bg.canvas.before:
            p = THEME_PALETTE[APP_CONFIG["current_theme"]]
            self.bg_color = Color(*p["bg"])
            self.rect = Rectangle(size=self.screen_bg.size, pos=self.screen_bg.pos)
        self.screen_bg.bind(size=self._update_rect, pos=self._update_rect)
        
        self.scroll_view = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.screen = Label(
            text="", font_name="Courier", font_size="11sp", color=p["txt"],
            halign="left", valign="top", size_hint_y=None
        )
        self.screen.bind(texture_size=self.screen.setter('size'))
        self.screen.bind(width=lambda inst, val: setattr(inst, 'text_size', (val, None)))
        
        self.scroll_view.add_widget(self.screen)
        self.screen_bg.add_widget(self.scroll_view)
        self.layout.add_widget(self.screen_bg)
        
        search_box = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=0.07)
        search_label = Label(text="🔍 Filter Log:", font_name="Courier", font_size="12sp", size_hint_x=0.3)
        self.search_input = TextInput(
            hint_text="Type phrase to filter (e.g. gps)", font_name="Courier",
            font_size="12sp", multiline=False, background_color=(0.15, 0.17, 0.22, 1),
            foreground_color=(1, 1, 1, 1), cursor_color=(1, 0.5, 0, 1)
        )
        self.search_input.bind(text=self.filter_logs_view)
        search_box.add_widget(search_label)
        search_box.add_widget(self.search_input)
        self.layout.add_widget(search_box)
        
        self.grid = GridLayout(cols=2, spacing=5, size_hint_y=0.45)
        self.btn_wifi = Button(text="📡 Wi-Fi [🟢]", background_color=(0.1, 0.15, 0.2, 1), on_press=self.open_wifi)
        self.btn_ble = Button(text="🔷 BLE [🟢]", background_color=(0.1, 0.15, 0.2, 1), on_press=self.open_ble)
        self.btn_voice = Button(text="🗣️ Voice [🟢]", background_color=(0.12, 0.2, 0.12, 1), on_press=self.run_voice)
        self.btn_haptic = Button(text="📳 Haptic [🟢]", background_color=(0.12, 0.2, 0.12, 1), on_press=self.run_haptic)
        self.btn_info = Button(text="📱 Dev Probe [🟢]", background_color=(0.2, 0.15, 0.1, 1), on_press=self.run_info)
        self.btn_stats = Button(text="📊 Metrics [🟢]", background_color=(0.2, 0.15, 0.1, 1), on_press=self.run_stats)
        self.btn_sat = Button(text="🛰️ GNSS [🟢]", background_color=(0.11, 0.11, 0.15, 1), on_press=self.run_gps)
        self.btn_strobe = Button(text="🔦 Strobe [🟢]", background_color=(0.11, 0.11, 0.15, 1), on_press=self.run_strobe)
        
        self.grid.add_widget(self.btn_wifi)
        self.grid.add_widget(self.btn_ble)
        self.grid.add_widget(self.btn_voice)
        self.grid.add_widget(self.btn_haptic)
        self.grid.add_widget(self.btn_info)
        self.grid.add_widget(self.btn_stats)
        self.grid.add_widget(self.btn_sat)
        self.grid.add_widget(self.btn_strobe)
        self.layout.add_widget(self.grid)
        
        nav_box = GridLayout(cols=3, spacing=5, size_hint_y=0.12)
        nav_box.add_widget(Button(text="⚙️ SETUP", background_color=(0.25, 0.25, 0.3, 1), on_press=self.go_settings))
        nav_box.add_widget(Button(text="🎨 SKIN", background_color=(0.25, 0.25, 0.3, 1), on_press=self.go_themes))
        nav_box.add_widget(Button(text="💾 EXPORT", background_color=(0.15, 0.35, 0.15, 1), on_press=self.export_terminal_logs))
        self.layout.add_widget(nav_box)
        
        self.add_widget(self.layout)
        self.strobe_active = False
        self.flash_on = False
        self.gps_active = False
        self.boot_percent = 0
        
        self.toggle_buttons(disable=True)
        Clock.schedule_once(self.trigger_boot, 0.2)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def toggle_buttons(self, disable=False):
        for btn in [self.btn_wifi, self.btn_ble, self.btn_voice, self.btn_haptic, self.btn_info, self.btn_stats, self.btn_sat, self.btn_strobe]:
            btn.disabled = disable

    def cmd_log(self, cmd_text, output_lines):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_block = f"[{timestamp}] root@titan:~# {cmd_text}\n"
        for line in output_lines:
            log_block += f" {line}\n"
            
        self.master_log_history.append(log_block)
        
        if len(self.master_log_history) > MAX_LOGS:
            self.master_log_history.pop(0)
            
        self.rebuild_display_view()

    def filter_logs_view(self, instance, value):
        self.rebuild_display_view()

    def rebuild_display_view(self):
        filter_text = self.search_input.text.lower().strip()
        if not filter_text:
            self.screen.text = "\n".join(self.master_log_history)
        else:
            filtered_list = [block for block in self.master_log_history if filter_text in block.lower()]
            self.screen.text = "\n".join(filtered_list) if filtered_list else "--- NO MATCHING LOG ENTRIES FOUND ---\n"
        Clock.schedule_once(lambda dt: setattr(self.scroll_view, 'scroll_y', 0), 0.05)

    def export_terminal_logs(self, instance):
        self.buzz(0.08)
        try:
            filename = "TitanLogs.txt"
            with open(filename, "w") as f:
                f.write("=== TITAN-FLIP CONSOLE SYSTEM LOGS ===\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("\n".join(self.master_log_history))
                
            path_output = os.path.abspath(filename)
            self.cmd_log("log-export", ["Log matrix written cleanly.", f"Location: {path_output}"])
        except Exception as e:
            self.cmd_log("log-export", [f"Export failed error context: {e}"])

    def buzz(self, duration=0.02):
        if APP_CONFIG["haptic_enabled"]:
            try:
                vibrator.vibrate(duration)
            except Exception:
                pass

    def trigger_boot(self, dt):
        Clock.schedule_interval(self.tick_boot, APP_CONFIG["boot_speed"])

    def tick_boot(self, dt):
        self.boot_percent += 5
        if self.boot_percent <= 100:
            bars = int(self.boot_percent / 10)
            progress = "█" * bars + "░" * (10 - bars)
            self.screen.text = f"🐬 TITAN-FLIP OS v7.5\n---------------------\nLoading peripheral RF matrices...\n\nSYSTEM KERNEL: {progress} {self.boot_percent}%"
        else:
            Clock.unschedule(self.tick_boot)
Use code with caution.self.screen.text = ""self.status_bar.text = "🟢 READY"self.status_bar.color = (0, 1, 0, 1)self.toggle_buttons(disable=False)self.cmd_log("sys-init", ["Kernel mapping complete.", "All device transceivers initialized."])if APP_CONFIG["sound_enabled"]:try:tts.speak("Titan ready.")except Exception as e:self.cmd_log("sys-init", [f"TTS Startup Fail: {e}"])
***

### Part 2: Main Operational Callbacks, Settings, and Themes Manager
Paste this second block right directly underneath Part 1 in the very same script file to finish it:

```python
    def open_wifi(self, instance):
        self.buzz()
        APP_CONFIG["stats"]["wifi"] += 1
        save_application_config()
        self.btn_wifi.text = "📡 Wi-Fi [🟡]"
        if Intent and Settings:
            try:
                PythonActivity.mActivity.startActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
                self.cmd_log("net-scan --wifi", ["Intent deployed.", "Opening system Wi-Fi panel."])
            except Exception as e:
                self.cmd_log("net-scan --wifi", [f"Invasive exception caught: {e}"])
        else:
            self.cmd_log("net-scan --wifi", ["Simulation target triggered connection sheet."])
        Clock.schedule_once(lambda dt: setattr(self.btn_wifi, 'text', "📡 Wi-Fi [🟢]"), 1.5)

    def open_ble(self, instance):
        self.buzz()
        APP_CONFIG["stats"]["ble"] += 1
        save_application_config()
        self.btn_ble.text = "🔷 BLE [🟡]"
        if Intent and Settings:
            try:
                PythonActivity.mActivity.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                self.cmd_log("rf-sweep --ble", ["Intent deployed.", "Opening system Bluetooth options."])
            except Exception as e:
                self.cmd_log("rf-sweep --ble", [f"Invasive exception caught: {e}"])
        else:
            self.cmd_log("rf-sweep --ble", ["Simulation target triggered peripheral manager."])
        Clock.schedule_once(lambda dt: setattr(self.btn_ble, 'text', "🔷 BLE [🟢]"), 1.5)

    def run_voice(self, instance):
        self.buzz(0.05)
        APP_CONFIG["stats"]["voice"] += 1
        save_application_config()
        self.btn_voice.text = "🗣️ Voice [🟡]"
        self.status_bar.text = "🟡 TRANSMITTING"
        self.status_bar.color = (1, 0.75, 0, 1)
        try:
            tts.speak("Titan engine operational.")
            self.cmd_log("audio-inject --tts", ["Voice modulation packet fired successfully."])
        except Exception as e:
            self.cmd_log("audio-inject --tts", [f"Bus exception caught: {e}"])
        self.status_bar.text = "🟢 READY"
        self.status_bar.color = (0, 1, 0, 1)
        self.btn_voice.text = "🗣️ Voice [🟢]"

    def run_haptic(self, instance):
        APP_CONFIG["stats"]["haptic"] += 1
        save_application_config()
        self.btn_haptic.text = "📳 Haptic [🟡]"
        try:
            vibrator.vibrate(0.2)
            self.cmd_log("motor-pulse --kinetic", ["Cycling internal balance weight motor.", "Pulse payload completed."])
        except Exception as e:
            self.cmd_log("motor-pulse --kinetic", [f"Bus exception caught: {e}"])
        self.btn_haptic.text = "📳 Haptic [🟢]"

    def run_info(self, instance):
        self.buzz()
        mfg, mdl, rel = "Samsung", "Galaxy A57 5G", "14/15"
        if Build and BuildVersion:
            try:
                mfg, mdl, rel = Build.MANUFACTURER, Build.MODEL, BuildVersion.RELEASE
            except Exception as e:
                self.cmd_log("device-probe", [f"Android API Probe Failure: {e}"])
        res = f"{Window.width}x{Window.height} Px"
        pct = "100%"
        try:
            pct = f"{battery.status.get('percentage', '100')}%"
        except Exception as e:
            self.cmd_log("device-probe", [f"Battery State Probe Failure: {e}"])
        self.cmd_log("device-probe", [
            f"Manufacturer : {mfg}", f"Phone Model  : {mdl}",
            f"Android OS   : Core v{rel}", f"Resolution   : {res}", f"Battery Grid : {pct}"
        ])

    def run_stats(self, instance):
        self.buzz()
        s = APP_CONFIG["stats"]
        self.cmd_log("sys-metrics", [
            f"Wi-Fi Panel Requests : {s['wifi']}", f"Bluetooth Scans     : {s['ble']}",
            f"Audio Injections    : {s['voice']}", f"Kinetic Haptic Waves: {s['haptic']}",
            f"Satellite Locks     : {s['gps']}", f"Optical Strobe Flashes: {s['strobe']}"
        ])

    def run_gps(self, instance):
        self.buzz()
        if not self.gps_active:
            APP_CONFIG["stats"]["gps"] += 1
            save_application_config()
            self.status_bar.text = "🟡 SEEKING"
            self.status_bar.color = (1, 0.75, 0, 1)
            self.btn_sat.text = "🛰️ GNSS [🔴]"
            self.cmd_log("gps-lock --init", ["Binding to overhead global satellite arrays...", "Awaiting positional tracking fix..."])
            try:
                gps.configure(on_location=self.on_location)
                gps.start()
                self.gps_active = True
            except Exception as e:
                self.cmd_log("gps-lock --init", [f"GNSS subsystem failure: {e}"])
                self.stop_gps_matrix()
        else:
            self.stop_gps_matrix()

    def on_location(self, **kwargs):
        self.cmd_log("gps-lock --recv", [f"Latitude: {kwargs.get('lat')}", f"Longitude: {kwargs.get('lon')}", f"Altitude: {kwargs.get('altitude')}m"])
        self.stop_gps_matrix()

    def stop_gps_matrix(self):
        try:
            gps.stop()
        except Exception as e:
            self.cmd_log("gps-lock --kill", [f"Exception stopping GPS array: {e}"])
        self.gps_active = False
        self.btn_sat.text = "🛰️ GNSS [🟢]"
        self.status_bar.text = "🟢 READY"
        self.status_bar.color = (0, 1, 0, 1)

    def run_strobe(self, instance):
        self.buzz()
        self.strobe_active = not self.strobe_active
        if self.strobe_active:
            APP_CONFIG["stats"]["strobe"] += 1
            save_application_config()
            self.status_bar.text = "🟡 TRANSMITTING"
            self.status_bar.color = (1, 0.75, 0, 1)
            self.btn_strobe.text = "🔦 Strobe [🔴]"
            self.cmd_log("strobe --engage", ["Closing circuit to high-gain camera LED beacon array."])
            Clock.schedule_interval(self.toggle_flash, 0.06)
        else:
            self.stop_strobe_matrix()

    def toggle_flash(self, dt):
        try:
            self.flash_on = not self.flash_on
            flash.on() if self.flash_on else flash.off()
        except Exception as e:
            Clock.unschedule(self.toggle_flash)
            self.cmd_log("strobe --error", [f"LED flash command failure: {e}"])

    def stop_strobe_matrix(self):
        self.strobe_active = False
        self.btn_strobe.text = "🔦 Strobe [🟢]"
        self.status_bar.text = "🟢 READY"
        self.status_bar.color = (0, 1, 0, 1)
        self.cmd_log("strobe --kill", ["Opening circuit. Optical transmitter array offline."])
        Clock.unschedule(self.toggle_flash)
        try:
            flash.off()
        except Exception:
            pass

    def update_theme_skin(self):
        p = THEME_PALETTE[APP_CONFIG["current_theme"]]
        self.bg_color.rgba = p["bg"]
        self.screen.color = p["txt"]

    def go_settings(self, inst):
        self.buzz()
        self.manager.current = 'settings'

    def go_themes(self, inst):
        self.buzz()
        self.manager.current = 'themes'


class SettingsScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=15, spacing=12)
        
        layout.add_widget(Label(text="⚙️ SYSTEM CONFIGURATION PANEL", font_name="Courier", font_size="14sp", size_hint_y=0.12))
        
        boot_lbl = "FAST"
        if APP_CONFIG["boot_speed"] == 0.01: boot_lbl = "INSTANT"
        elif APP_CONFIG["boot_speed"] == 0.08: boot_lbl = "SLOW/RETR"
        
        self.btn_boot = Button(text=f"Boot Loader Speed: {boot_lbl}", size_hint_y=0.15)
        self.btn_boot.bind(on_press=self.toggle_boot_speed)
        layout.add_widget(self.btn_boot)
        
        haptic_row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        haptic_row.add_widget(Label(text="Haptic Buzz Response:", font_name="Courier", font_size="12sp", halign="left"))
        self.switch_vib = Switch(active=APP_CONFIG["haptic_enabled"])
        self.switch_vib.bind(active=self.on_vibrate_switch)
        haptic_row.add_widget(self.switch_vib)
        layout.add_widget(haptic_row)
        
        sound_row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        sound_row.add_widget(Label(text="Startup Audio Synthesis:", font_name="Courier", font_size="12sp", halign="left"))
        self.switch_snd = Switch(active=APP_CONFIG["sound_enabled"])
        self.switch_snd.bind(active=self.on_sound_switch)
        sound_row.add_widget(self.switch_snd)
        layout.add_widget(sound_row)
        
        layout.add_widget(BoxLayout(size_hint_y=0.13))
        
        layout.add_widget(Button(text="📟 RETURN TO MAIN TERMINAL", background_color=(0.5, 0.1, 0.1, 1), size_hint_y=0.15, on_press=self.go_back))
        self.add_widget(layout)

    def toggle_boot_speed(self, inst):
        if APP_CONFIG["boot_speed"] == 0.04:
            APP_CONFIG["boot_speed"] = 0.01
            self.btn_boot.text = "Boot Loader Speed: INSTANT"
        elif APP_CONFIG["boot_speed"] == 0.01:
            APP_CONFIG["boot_speed"] = 0.08
            self.btn_boot.text = "Boot Loader Speed: SLOW/RETR"
        else:
            APP_CONFIG["boot_speed"] = 0.04
            self.btn_boot.text = "Boot Loader Speed: FAST"
        save_application_config()

    def on_vibrate_switch(self, instance, value):
        APP_CONFIG["haptic_enabled"] = value
        save_application_config()

    def on_sound_switch(self, instance, value):
        APP_CONFIG["sound_enabled"] = value
        save_application_config()

    def go_back(self, inst):
        self.manager.current = 'terminal'


class ThemesScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=15, spacing=10)
layout.add_widget(Label(text="🎨 HARDWARE MATRIX SKIN ENGINE", font_name="Courier", font_size="14sp", size_hint_y=0.15))grid = GridLayout(cols=2, spacing=8, size_hint_y=0.7)for theme_name in THEME_PALETTE.keys():grid.add_widget(Button(text=theme_name, on_press=self.apply_theme))layout.add_widget(grid)layout.add_widget(Button(text="📟 RETURN TO MAIN TERMINAL", background_color=(0.5, 0.1, 0.1, 1), size_hint_y=0.15, on_press=self.go_back))self.add_widget(layout)def apply_theme(self, instance):APP_CONFIG["current_theme"] = instance.textsave_application_config()terminal_scr = self.manager.get_screen('terminal')terminal_scr.update_theme_skin()terminal_scr.cmd_log("skin-load", [f"Interface skin changed to profile: {instance.text}"])self.manager.current = 'terminal'def go_back(self, inst):self.manager.current = 'terminal'class FlipperApp(App):def build(self):load_application_config()sm = ScreenManager()t_screen = TerminalScreen(name='terminal')t_screen.update_theme_skin()sm.add_widget(t_screen)sm.add_widget(SettingsScreen(name='settings'))sm.add_widget(ThemesScreen(name='themes'))return smif name == 'main':FlipperApp().run()
