# Terminal demo for vhs (https://github.com/charmbracelet/vhs).
# Re-record whenever the CLI output changes:
#   vhs docs/demo.tape
Output docs/demo.gif
Set FontSize 14
Set Width 1200
Set Height 600
Set TypingSpeed 40ms
Set Theme "Catppuccin Mocha"

Hide
Type "clear"
Enter
Show

Type "uv run mm run rq1 -c configs/rq1.yaml --fixture"
Enter
Sleep 4s

Type "uv run mm readme"
Enter
Sleep 1s

Type "# Live BIRD runs: see results/rq1 and results/rq2 plots above"
Enter
Sleep 2s
