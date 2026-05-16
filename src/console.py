# msg bus for TUI
# from src.console import console

from datetime import datetime

class Console:
    def __init__(self):
        self.widget = None

    def attach(self, widget) -> None:
        self.widget = widget

    def log(self, message: str) -> None:

        # timestamp(May it will remove later)
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"{timestamp}\n{message}"

        ## 沒啟動print到cli, 有啟動丟到tui
        if self.widget is not None:
            self.widget.write(line)
        else:
            print(line)

# 給其他script用
console = Console()
