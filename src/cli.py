"""TUI front-end for the Tiles Survive ADB controller (Windows, list-style menu)."""
import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Static, RichLog, ListView, ListItem, Label
from textual.reactive import reactive

from adb_client import (
    AdbError,
    connect_bluestacks,
    list_devices_raw,
    scan_bluestacks,
    disconnect,
    disconnect_all,
)
from action.screenshot import screenshot_and_show
from strategies import kill_zombie_leader

IMAGE_PATH = Path(__file__).resolve().parents[1] / "image_templetes" / "open_it.png"
MAX_LOG_LINES = 50

# Spinner config — Braille frames are the de facto Linux standard for inline spinners.
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_INTERVAL = 0.08                              # seconds per frame

# State machine modes for the single ListView widget.
MODE_MAIN       = "main"
MODE_DEVICES    = "devices"
MODE_ACTIONS    = "actions"
MODE_STRATEGIES = "strategies"


class TilesSurviveApp(App):
    CSS = """
    Screen { layout: vertical; }
    #main         { height: 1fr; padding: 1 2; }
    #logbox       { height: 12; border: solid grey; }
    RichLog       { background: black; color: white; }
    ListView      { height: auto; max-height: 12; border: solid grey; margin-top: 1; }
    .title        { text-style: bold; padding-bottom: 1; }
    #status_line  { color: cyan; padding: 0 0 1 0; min-height: 1; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    selected_device: reactive[str] = reactive("(none)")

    def __init__(self) -> None:
        super().__init__()
        self._mode: str = MODE_MAIN
        self._devices: list[tuple[str, str]] = []

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="main"):
            yield Static(id="device_bar")
            yield Static(id="instructions", classes="title")
            yield Static(id="status_line")
            yield ListView(id="menu")
        with Vertical(id="logbox"):
            yield RichLog(id="logs", max_lines=MAX_LOG_LINES, wrap=False, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_device_bar()
        self.show_main_menu()
        self.log_line("[green]App started.[/]  Use ↑/↓ + Enter to choose.")

    # ---------- helpers ----------
    def log_line(self, msg: str) -> None:
        self.query_one("#logs", RichLog).write(msg)

    def refresh_device_bar(self) -> None:
        self.query_one("#device_bar", Static).update(
            f"[b]Connected device:[/] {self.selected_device}"
        )

    def _set_menu(self, instructions: str, items: list[tuple[str, str]]) -> None:
        """Replace instructions + ListView contents in one shot."""
        self.query_one("#instructions", Static).update(instructions)
        menu = self.query_one("#menu", ListView)
        menu.clear()
        for item_id, label in items:
            menu.append(ListItem(Label(label), id=item_id))

    # ---------- spinner ----------
    def _start_spinner(self, message: str) -> None:
        """Begin animating '<spinner> <message>' on the status line."""
        self._spinner_idx = 0
        self._spinner_message = message
        self._spinner_timer = self.set_interval(SPINNER_INTERVAL, self._tick_spinner)
        self._tick_spinner()                          # paint first frame immediately

    def _tick_spinner(self) -> None:
        frame = SPINNER_FRAMES[self._spinner_idx % len(SPINNER_FRAMES)]
        self._spinner_idx += 1
        self.query_one("#status_line", Static).update(
            f"[cyan]{frame}[/] {self._spinner_message}"
        )

    def _stop_spinner(self) -> None:
        timer = getattr(self, "_spinner_timer", None)
        if timer is not None:
            timer.stop()
            self._spinner_timer = None
        self.query_one("#status_line", Static).update("")

    # ---------- menu builders ----------
    def show_main_menu(self) -> None:
        self._mode = MODE_MAIN
        self._set_menu(
            "Step 1: Open BlueStacks and launch the game.\n"
            "Step 2: Enable ADB in Settings → Advanced.",
            [
                ("opt_show_img", "Show screenshot   —  open setup hint in image viewer"),
                ("opt_prepared", "Prepared          —  scan & pick a device"),
                ("opt_quit",     "Not yet           —  quit"),
            ],
        )

    def show_device_menu(self, devices: list[tuple[str, str]]) -> None:
        self._mode = MODE_DEVICES
        self._devices = devices
        items = [(f"dev_{i}", f"{serial}   [{state}]")
                 for i, (serial, state) in enumerate(devices)]
        items.append(("opt_back_main", "← Back"))
        self._set_menu("Pick a device:", items)

    def show_action_menu(self) -> None:
        self._mode = MODE_ACTIONS
        self._set_menu(
            f"Connected to [b]{self.selected_device}[/].  Choose an action:",
            [
                ("act_screenshot", "Screenshot       —  capture & view for 5s"),
                ("act_strategy",   "Run strategy     —  pick a strategy"),
                ("act_disconnect", "Disconnect       —  back to device picker"),
                ("act_quit",       "Quit"),
            ],
        )

    def show_strategy_menu(self) -> None:
        self._mode = MODE_STRATEGIES
        self._set_menu(
            "Pick a strategy to run:",
            [
                ("strat_kill_zombie_leader", "Kill Zombie Leader"),
                ("opt_back_actions",         "← Back"),
            ],
        )

    # ---------- list selection dispatcher ----------
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        match self._mode:
            case "main":
                self._handle_main(item_id)
            case "devices":
                self._handle_devices(item_id)
            case "actions":
                self._handle_actions(item_id)
            case "strategies":
                self._handle_strategies(item_id)

    def _handle_main(self, item_id: str) -> None:
        if item_id == "opt_show_img":
            self.open_screenshot_hint()
        elif item_id == "opt_prepared":
            self.scan_and_show_devices()
        elif item_id == "opt_quit":
            self.exit()

    def _handle_devices(self, item_id: str) -> None:
        if item_id.startswith("dev_"):
            idx = int(item_id.split("_")[1])
            serial, _ = self._devices[idx]
            self.connect_to(serial)
        elif item_id == "opt_back_main":
            self.show_main_menu()

    def _handle_actions(self, item_id: str) -> None:
        if item_id == "act_screenshot":
            self.action_screenshot()
        elif item_id == "act_strategy":
            self.show_strategy_menu()
        elif item_id == "act_disconnect":
            self.action_disconnect()
        elif item_id == "act_quit":
            self.exit()

    def _handle_strategies(self, item_id: str) -> None:
        if item_id == "strat_kill_zombie_leader":
            self.action_run_strategy(kill_zombie_leader)
        elif item_id == "opt_back_actions":
            self.show_action_menu()

    # ---------- actions ----------
    def open_screenshot_hint(self) -> None:
        if not IMAGE_PATH.exists():
            self.log_line(f"[red]Image not found:[/] {IMAGE_PATH}")
            return
        try:
            os.startfile(str(IMAGE_PATH))             # Windows-only API
            self.log_line(f"[cyan]Opened[/] {IMAGE_PATH.name} in default viewer.")
        except OSError as e:
            self.log_line(f"[red]Cannot open image:[/] {e}")

    def scan_and_show_devices(self) -> None:
        """Kick off the background scan; the worker handles UI updates."""
        self.log_line("[cyan]Scanning BlueStacks ports...[/]")
        self._start_spinner("Scanning...")
        self._scan_worker()

    @work(thread=True, exclusive=True)
    def _scan_worker(self) -> None:
        """Runs in a background thread so the TUI stays responsive."""
        try:
            scan_bluestacks()
        except AdbError as e:
            self.app.call_from_thread(self.log_line, f"[red]Scan failed:[/] {e}")
            self.app.call_from_thread(self._stop_spinner)
            return
        devices = list_devices_raw()
        self.app.call_from_thread(self._after_scan, devices)

    def _after_scan(self, devices: list[tuple[str, str]]) -> None:
        """Called on the UI thread once the worker finishes."""
        self._stop_spinner()
        if not devices:
            self.log_line("[red]No devices found.[/] Confirm BlueStacks + ADB are on.")
            return
        self.log_line(f"[green]Scan complete.[/] Found {len(devices)} device(s).")
        self.show_device_menu(devices)

    def connect_to(self, serial: str) -> None:
        host, _, port_str = serial.partition(":")
        self.log_line(f"Connecting to {serial}...")
        try:
            confirmed = connect_bluestacks(host=host, port=int(port_str))
        except AdbError as e:
            self.log_line(f"[red][FAIL][/] {e}")
            return
        self.selected_device = confirmed
        self.refresh_device_bar()
        self.log_line(f"[green][OK][/] Connected to {confirmed}")
        self.show_action_menu()

    def action_disconnect(self) -> None:
        if self.selected_device != "(none)":
            disconnect(self.selected_device)
            self.log_line(f"[yellow]Disconnected[/] {self.selected_device}.")
        self.selected_device = "(none)"
        self.refresh_device_bar()
        self.show_main_menu()

    def action_screenshot(self) -> None:
        if self.selected_device == "(none)":
            self.log_line("[red]No device connected.[/]")
            return
        self.log_line("Capturing screenshot...")
        try:
            screenshot_and_show(self.selected_device)
        except Exception as e:
            self.log_line(f"[red]Screenshot failed:[/] {e}")
            return
        self.log_line("[cyan]Screenshot window will close in 5s.[/]")

    def action_run_strategy(self, strategy_module) -> None:
        name = getattr(strategy_module, "NAME", strategy_module.__name__)
        self.log_line(f"Running strategy: [b]{name}[/]")
        try:
            strategy_module.run(self.selected_device)
            self.log_line(f"[green]Strategy '{name}' finished.[/]")
        except NotImplementedError as e:
            self.log_line(f"[yellow]{e}[/]")
        except Exception as e:
            self.log_line(f"[red]Strategy error:[/] {e}")

    def on_unmount(self) -> None:
        disconnect_all()


def main() -> None:
    TilesSurviveApp().run()


if __name__ == "__main__":
    main()
