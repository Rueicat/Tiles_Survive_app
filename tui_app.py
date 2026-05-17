from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import Button, Static, Select, RichLog, Header, Footer
from textual import work

# My modules
from src.console import console
from src.adb_client_v2 import connect_bluestacks, disconnect_all
from src.actions.outside_mv import go_to_wild


#-------config
VM_PORTS = [5555, 5575,5565, 5595, 5605]

## 清單
ACTIONS = {
    "出城": go_to_wild,
}

USER_NOTE = """\
NOTE: 
1. 記得先把模擬器進階功能中的"ADB"功能開啟
2. 右邊有log, 可以幫忙看我那邊怪怪的 
"""

# chinese name map(in the code using)
STATE_DISCONNECTED = "disconnected"
STATE_CONNECTED = "connected"
STATE_RUNNING = "running"
STATE_ERROR = "error"

# on the UI
STATE_DISPLAY = {
    STATE_DISCONNECTED:("未連線", "white"),
    STATE_CONNECTED:("已連線", "green"),
    STATE_RUNNING:("執行中", "yellow"),
    STATE_ERROR:("錯誤", "red"),
}



#--------MAIN

class AutorunApp(App):
    """TUI for controlling multi-VM BlueStacks automation."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    #left-pane {
        width: 3fr;
        height: 100%;
        border: solid white;
        padding: 1;
    }

    #right-pane {
        width: 2fr;
        height: 100%;
        border: solid green;
        padding: 1;
    }

    #note {
        height: 5;
        border: solid yellow;
        padding: 0 1;
    }

    #controls {
        height: 3;
        margin-bottom: 1;
    }

    #controls Button, #controls Select {
        margin-right: 1;
    }

    #vm-grid {
        grid-size: 2 6;
        grid-columns: 1fr 1fr;
        grid-rows: 3;
        height: auto;
    }

    .vm-cell {
        border: solid white;
        content-align: center middle;
        height: 3;
    }

    #log-pane {
        height: 100%;
        border: solid cyan;
    }
    """

    def __init__(self):
        super().__init__()

        self.vm_states: dict[int, str] = {p: STATE_DISCONNECTED for p in VM_PORTS}
        # widget refs we update later
        self.state_widgets: dict[int, Static] = {}
        self.scope_select: Select | None = None
        self.action_select: Select | None = None
        self.log_widget: RichLog | None = None

    # ----------------------------------------------------------
    # Build the widget tree
    # 宣告式, 這領域先用AI, 之後再換熟悉的框架
    # ----------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # ---------- LEFT PANE ----------
        with Vertical(id="left-pane"):
            yield Static(USER_NOTE, id="note")

            # controls row
            with Horizontal(id="controls"):
                yield Button("START", id="btn-start", variant="success")
                yield Select(
                    [("none", "none")],
                    prompt="scope",
                    id="scope-select",
                    disabled=True,
                )
                yield Select(
                    [(name, name) for name in ACTIONS.keys()],
                    prompt="action",
                    id="action-select",
                )
                yield Button("RUN", id="btn-run", variant="primary", disabled=True)

            # VM status grid
            with Grid(id="vm-grid"):
                yield Static("虛擬機", classes="vm-cell")
                yield Static("狀態", classes="vm-cell")
                for port in VM_PORTS:
                    yield Static(f"VM:{port}", classes="vm-cell")
                    state_w = Static("", classes="vm-cell")
                    self.state_widgets[port] = state_w
                    yield state_w

        # ---------- RIGHT PANE ----------
        with Vertical(id="right-pane"):
            self.log_widget = RichLog(
                id="log-pane",
                max_lines=50,        # Linux-tail style: keep last 50 lines
                markup=True,         # enable [red]...[/red] color tags
                wrap=True,
            )
            yield self.log_widget

        yield Footer()

    # ----------狀態
    def on_mount(self) -> None:
        console.attach(self.log_widget)
        self.scope_select = self.query_one("#scope-select", Select)
        self.action_select = self.query_one("#action-select", Select)

        for port in VM_PORTS:
            self._update_state_cell(port)

        console.log("請按'START'連線模擬器")

    # ----------------------------------------------------------
    # Button handlers
    # ----------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            # toggle behavior
            if str(event.button.label) == "START":
                event.button.label = "STOP"
                self.connect_all_vms()
            else:
                event.button.label = "START"
                self.disconnect_all_vms()

        elif event.button.id == "btn-run":
            self.run_action()

    ##----select changed
    def on_select_changed(self, event: Select.Changed) -> None:
        scope_val = self.scope_select.value
        action_val = self.action_select.value
        
        scope_ok = scope_val not in (Select.BLANK, "none")
        action_ok = action_val is not Select.BLANK
        
        self.query_one("#btn-run", Button).disabled = not (scope_ok and action_ok)

    # ----------------------------------------------------------
    # Connect all VMs (background thread so UI doesn't freeze)
    # ----------------------------------------------------------
    @work(thread=True, group="connect")
    def connect_all_vms(self) -> None:
        console.log("連線五台虛擬機中...\nport:5555-5559")
        connected = []

        for port in VM_PORTS:
            console.log(f"trying {port}...")
            ok, msg = connect_bluestacks(port=port)

            if ok:
                self.vm_states[port] = STATE_CONNECTED
                connected.append(port)
                console.log(f"[green]OK[/green] {port}:{msg}")
            else:
                self.vm_states[port] = STATE_ERROR
                console.log(f"[red]FAIL[/red] {port}: {msg}")

            # UI updates must run on the main thread
            self.call_from_thread(self._update_state_cell, port)

        self.call_from_thread(self._refresh_scope_select, connected)

        if connected:
            console.log(f"[green]Done.[/green]. 已連線: {connected}")
        else:
            console.log("[red]No VM connected.[/red] Check BlueStacks/ADB.")

    @work(thread=True, group="connect")
    def disconnect_all_vms(self) -> None:
        console.log("切斷全部連線中...")
        
        ok, msg = disconnect_all()
        if ok:
            console.log(f"[green]{msg}[/green]")
        else:
            console.log(f"[red]錯誤:{msg}[/red]")
            
        for port in VM_PORTS:
            self.vm_states[port] = STATE_DISCONNECTED
            self.call_from_thread(self._update_state_cell,port)

        self.call_from_thread(self._refresh_scope_select, [])

    # ----------------------------------------------------------
    # UI update helpers (call from main thread only)
    # ----------------------------------------------------------
    def _update_state_cell(self, port: int) -> None:
        state = self.vm_states[port]
        text, color = STATE_DISPLAY.get(state, ("?", "white"))
        self.state_widgets[port].update(f"[{color}]{text}[/{color}]")

    def _refresh_scope_select(self, connected_ports: list[int]) -> None:
        if not connected_ports:
            self.scope_select.set_options([("none", "none")])
            self.scope_select.disabled = True
            self.query_one("#btn-run", Button).disabled = True
            return

        options = [("all", "all")]
        options += [(f"VM:{p}", str(p)) for p in connected_ports]
        self.scope_select.set_options(options)
        self.scope_select.disabled = False

    # ----------------------------------------------------------
    # RUN: dispatch action to one or all VMs
    # ----------------------------------------------------------
    def run_action(self) -> None:
        scope_val = self.scope_select.value
        action_name = self.action_select.value

        if scope_val is Select.BLANK or action_name is Select.BLANK:
            console.log("[yellow]請先選擇scope和action.[/yellow]")
            return

        # resolve scope to a list of ports
        if scope_val == "all":
            targets = [p for p, s in self.vm_states.items() if s == STATE_CONNECTED]
        else:
            targets = [int(scope_val)]

        action_fn = ACTIONS[action_name]
        console.log(f"執行 '{action_name}' on {targets}")

        # one worker per VM, so they run in parallel
        for port in targets:
            self._run_action_worker(port, action_fn, action_name)

    @work(thread=True, group="action")
    def _run_action_worker(self, port: int, action_fn, action_name: str) -> None:
        device = f"127.0.0.1:{port}"
        self.vm_states[port] = STATE_RUNNING
        self.call_from_thread(self._update_state_cell, port)
        console.log(f"[{device}] 開始 '{action_name}'...")

        try:
            result = action_fn(device)
            console.log(f"  [{device}] {result}")
            self.vm_states[port] = STATE_CONNECTED
        except Exception as e:
            # show the error in the log pane
            console.log(f"  [red][{device}] ERROR: {e}[/red]")
            self.vm_states[port] = STATE_ERROR

        self.call_from_thread(self._update_state_cell, port)


# --------------------------------------------------------------
# Entry point
# --------------------------------------------------------------
if __name__ == "__main__":
    AutorunApp().run()
