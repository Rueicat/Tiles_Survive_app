from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import Button, Static, Select, RichLog, Header, Footer
from textual import work

# My modules
from src.console import console
from src.adb_client_v2 import (
    connect_discovered_vms,
    disconnect_all,
    MAX_VMS,
)
from src.actions.outside_mv import go_to_wild


#-------config
NUM_SLOTS = MAX_VMS  # = 5

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
STATE_EMPTY = "empty"   # ← 新增: slot 沒被分配到 port 時用

# on the UI
STATE_DISPLAY = {
    STATE_DISCONNECTED:("未連線", "white"),
    STATE_CONNECTED:("已連線", "green"),
    STATE_RUNNING:("執行中", "yellow"),
    STATE_ERROR:("錯誤", "red"),
    STATE_EMPTY:        ("",       "white"),  # ← 空白
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
        overflow-y: auto;
        overflow-x: hidden;
    }
    """

    def __init__(self):
        super().__init__()

        # slot_to_port[i] = port  ; 沒分配到 port 的 slot 是 None
        # 用 list 而不是 dict, 因為 slot 是固定 5 個有序位置
        self.slot_to_port: list[int | None] = [None] * NUM_SLOTS

        # 每個 port 目前的狀態
        self.vm_states: dict[int, str] = {}

        # slot 左邊的 "VM:xxxx" label widget (5 個)
        self.label_widgets: list[Static] = []
        # slot 右邊的狀態 widget (5 個)
        self.state_widgets: list[Static] = []

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
                    [],                  # 空 options, allow_blank 預設 True
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

            # VM status grid: 固定 5 個 slot, port label 啟動時先用 "---" 佔位
            with Grid(id="vm-grid"):
                yield Static("虛擬機", classes="vm-cell")
                yield Static("狀態", classes="vm-cell")
                for _ in range(NUM_SLOTS):
                    label_w = Static("---", classes="vm-cell")
                    self.label_widgets.append(label_w)
                    yield label_w

                    state_w = Static("", classes="vm-cell")
                    self.state_widgets.append(state_w)
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
        self.log_widget.can_focus = False
        self.scope_select = self.query_one("#scope-select", Select)
        self.action_select = self.query_one("#action-select", Select)

        # 啟動時 5 個 slot 都空白
        for i in range(NUM_SLOTS):
            self._update_slot_cell(i)

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
            self._run_selected_action()

    ##----select changed
    def on_select_changed(self, event: Select.Changed) -> None:
        self._refresh_run_button()

    def _refresh_run_button(self) -> None:
        """
        RUN 開放條件: scope 是合法的 (已連線 port 或 'all'), 且 action 是 ACTIONS key.
        完全不依賴 Select.NULL / Select.BLANK 等 sentinel.
        """
        run_btn = self.query_one("#btn-run", Button)
        run_btn.disabled = not self._can_run()

    def _can_run(self) -> bool:
        """檢查目前 scope + action 狀態能不能執行."""
        # action 必須是 ACTIONS dict 的合法 key
        action_val = self.action_select.value if self.action_select else None
        if action_val not in ACTIONS:
            return False

        # scope 必須是 "all" 或者 已連線 port 的字串
        scope_val = self.scope_select.value if self.scope_select else None
        valid_scopes = self._valid_scope_values()
        if scope_val not in valid_scopes:
            return False

        return True

    def _valid_scope_values(self) -> set[str]:
        """目前 scope select 能合法接受的值 (whitelist)."""
        connected_ports = [
            p for p, s in self.vm_states.items() if s == STATE_CONNECTED
        ]
        if not connected_ports:
            return set()
        # "all" + 每個 connected port 的字串形式
        return {"all"} | {str(p) for p in connected_ports}

    # ----------------------------------------------------------
    # Connect all VMs (background thread so UI doesn't freeze)
    # ----------------------------------------------------------
    @work(thread=True, group="connect")
    def connect_all_vms(self) -> None:
        console.log("掃描 BlueStacks 設定中...")

        # progress callback: adb_client 每連一台就 log 一次
        def progress(port: int, ok: bool, info: str) -> None:
            if ok:
                console.log(f"[green]OK[/green] {port}")
            else:
                console.log(f"[red]FAIL[/red] {port}:\n {info}")

        # 探索 + 連線 (最多 MAX_VMS 台)
        connected, failed, msg = connect_discovered_vms(
            on_progress=progress,
            max_vms=MAX_VMS,
        )
        console.log(msg)

        # 把成功的 port 依序填進 slot 0~N, 剩下的 slot 保持空白
        self.slot_to_port = [None] * NUM_SLOTS
        self.vm_states = {}
        for i, port in enumerate(connected):
            self.slot_to_port[i] = port
            self.vm_states[port] = STATE_CONNECTED

        # 更新所有 slot 的顯示 (main thread)
        for i in range(NUM_SLOTS):
            self.call_from_thread(self._update_slot_cell, i)

        self.call_from_thread(self._refresh_scope_select, connected)
        self.call_from_thread(self._refresh_run_button)

        if connected:
            console.log(f"[green]Done.[/green] 已連線: {connected}")
        else:
            console.log("[red]No VM connected.[/red]\n Check BlueStacks/ADB.")

    @work(thread=True, group="connect")
    def disconnect_all_vms(self) -> None:
        console.log("切斷全部連線中...")
        
        ok, msg = disconnect_all()
        if ok:
            console.log(f"[green]{msg}[/green]")
        else:
            console.log(f"[red]錯誤:{msg}[/red]")

        # 把每個有 port 的 slot 標成未連線
        for i, port in enumerate(self.slot_to_port):
            if port is not None:
                self.vm_states[port] = STATE_DISCONNECTED
                self.call_from_thread(self._update_slot_cell, i)

        self.call_from_thread(self._refresh_scope_select, [])
        self.call_from_thread(self._refresh_run_button)

    # ----------------------------------------------------------
    # UI update helpers (call from main thread only)
    # ----------------------------------------------------------
    def _update_slot_cell(self, slot_idx: int) -> None:
        """根據 slot_to_port[i] 和 vm_states 更新該 slot 的 label + 狀態."""
        port = self.slot_to_port[slot_idx]

        if port is None:
            # 沒分配到 port 的 slot: 顯示空白
            self.label_widgets[slot_idx].update("---")
            text, color = STATE_DISPLAY[STATE_EMPTY]
            self.state_widgets[slot_idx].update(f"[{color}]{text}[/{color}]")
            return

        # 有 port: 顯示實際 port number + 狀態顏色
        self.label_widgets[slot_idx].update(f"VM:{port}")
        state = self.vm_states.get(port, STATE_DISCONNECTED)
        text, color = STATE_DISPLAY.get(state, ("?", "white"))
        self.state_widgets[slot_idx].update(f"[{color}]{text}[/{color}]")

    def _port_to_slot(self, port: int) -> int | None:
        """找出某個 port 在第幾個 slot (給 action worker 用)."""
        for i, p in enumerate(self.slot_to_port):
            if p == port:
                return i
        return None

    def _refresh_scope_select(self, connected_ports: list[int]) -> None:
        if not connected_ports:
            self.scope_select.set_options([])
            self.scope_select.disabled = True
            return

        options = [("all", "all")]
        options += [(f"VM:{p}", str(p)) for p in connected_ports]
        self.scope_select.set_options(options)
        self.scope_select.disabled = False

    # ----------------------------------------------------------
    # RUN dispatcher
    # ----------------------------------------------------------
    def _run_selected_action(self) -> None:
        """
        執行 RUN. 內部用 whitelist 二度驗證, 不信任 UI disabled 狀態.
        """
        # 二度檢查: 完全不依賴 button 的 disabled
        if not self._can_run():
            console.log("[yellow]請先選擇 scope 和 action.[/yellow]")
            return

        scope_val = self.scope_select.value
        action_name = self.action_select.value

        # 到這裡, _can_run() 已經保證 scope_val 是 "all" 或合法 port 字串
        if scope_val == "all":
            targets = [
                p for p, s in self.vm_states.items() if s == STATE_CONNECTED
            ]
        else:
            # 因為 _can_run() 已經過 whitelist, 這裡 int() 一定安全
            targets = [int(scope_val)]

        if not targets:
            console.log("[yellow]沒有可執行的 VM.[/yellow]")
            return

        action_fn = ACTIONS[action_name]
        console.log(f"執行 '{action_name}' on {targets}")

        # one worker per VM, so they run in parallel
        for port in targets:
            self._run_action_worker(port, action_fn, action_name)

    @work(thread=True, group="action")
    def _run_action_worker(self, port: int, action_fn, action_name: str) -> None:
        device = f"127.0.0.1:{port}"
        slot_idx = self._port_to_slot(port)

        self.vm_states[port] = STATE_RUNNING
        if slot_idx is not None:
            self.call_from_thread(self._update_slot_cell, slot_idx)
        console.log(f"[{port}] 開始 '{action_name}'...")

        try:
            result = action_fn(device)
            console.log(f"  [{port}] {result}")
            self.vm_states[port] = STATE_CONNECTED
        except Exception as e:
            # show the error in the log pane
            console.log(f"  [red][{port}] ERROR: {e}[/red]")
            self.vm_states[port] = STATE_ERROR

        if slot_idx is not None:
            self.call_from_thread(self._update_slot_cell, slot_idx)


# --------------------------------------------------------------
# Entry point
# --------------------------------------------------------------
if __name__ == "__main__":
    AutorunApp().run()
