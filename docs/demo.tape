# Terminal demo for vhs. Re-record with:
#   PATH="$HOME/.local/bin:$HOME/go/bin:$PATH" vhs docs/demo.tape
Output docs/demo.gif
Set Shell "zsh"
Set FontSize 15
Set Width 1280
Set Height 720
Set TypingSpeed 35ms
Set Theme "Catppuccin Mocha"
Set Padding 16
Set Margin 0
Set Framerate 24
Set PlaybackSpeed 1.0

Hide
Type "cd /media/rohitanand/Rohit/Personal/Workspace/metadata-matters"
Enter
Type "clear"
Enter
Show

Type "# Metadata Matters — catalog metadata vs text-to-SQL"
Enter
Sleep 800ms

Type "uv run mm run rq1 -c configs/rq1.yaml --fixture --dry-run"
Enter
Sleep 3s

Type "uv run mm run rq1 -c configs/rq1.yaml --fixture"
Enter
Sleep 8s

Type "uv run mm readme"
Enter
Sleep 2s

Type "sed -n '/results:start/,/results:end/p' README.md"
Enter
Sleep 2s

Type "head -n 12 results/rq1/20261002T172038Z-0d9ae03c/metrics.csv"
Enter
Sleep 2s

Type "head -n 8 results/rq2/20261002T182441Z-bf771428/metrics.csv"
Enter
Sleep 3s
