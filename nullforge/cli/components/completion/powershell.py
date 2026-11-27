"""PowerShell shell-completion support."""

import os
import re
from typing import Final

from click.shell_completion import CompletionItem, ShellComplete, add_completion_class


SOURCE_POWERSHELL: Final[str] = """\
$%(complete_func)s = {
    param($wordToComplete, $commandAst, $cursorPosition)
    $env:%(complete_var)s = "powershell_complete"
    $env:%(complete_var)s_WORDS = $commandAst.ToString()
    $env:%(complete_var)s_INCOMPLETE = "$wordToComplete"
    try {
        & "%(prog_name)s" 2>$null | ForEach-Object {
            $type, $value, $help = $_ -split "`t", 3
            if ($type -eq "plain") {
                $completionText = if ($value -match "\\s") { '"' + $value + '"' } else { $value }
                $tooltip = if ($help) { $help } else { $value }
                [System.Management.Automation.CompletionResult]::new(
                    $completionText, $value, "ParameterValue", $tooltip)
            }
            elseif (($type -eq "file") -or ($type -eq "dir")) {
                Get-ChildItem -Path "$wordToComplete*" -ErrorAction SilentlyContinue | ForEach-Object {
                    [System.Management.Automation.CompletionResult]::new(
                        $_.FullName, $_.Name, "ProviderItem", $_.Name)
                }
            }
        }
    }
    finally {
        Remove-Item Env:%(complete_var)s, Env:%(complete_var)s_WORDS, Env:%(complete_var)s_INCOMPLETE `
            -ErrorAction SilentlyContinue
    }
}
Register-ArgumentCompleter -Native -CommandName "%(prog_name)s", "%(prog_name)s.exe" `
    -ScriptBlock $%(complete_func)s
"""

TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r'"[^"]*"?|\'[^\']*\'?|\S+')


def split_powershell_line(line: str) -> list[str]:
    """Split PowerShell command line into words, keeping backslashes literal."""

    tokens: list[str] = []
    for match in TOKEN_PATTERN.finditer(line):
        token = match.group()
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
            token = token[1:-1]
        elif token[:1] in {'"', "'"}:
            token = token[1:]
        tokens.append(token)
    return tokens


class PowerShellComplete(ShellComplete):
    """Completion for Windows PowerShell 5+ and pwsh."""

    name = "powershell"
    source_template = SOURCE_POWERSHELL

    def get_completion_args(self) -> tuple[list[str], str]:
        line = os.environ.get(f"{self.complete_var}_WORDS", "")
        incomplete = os.environ.get(f"{self.complete_var}_INCOMPLETE", "")
        args = split_powershell_line(line)[1:]
        if incomplete and args and args[-1] == incomplete:
            args.pop()
        return args, incomplete

    def format_completion(self, item: CompletionItem) -> str:
        return f"{item.type}\t{item.value}\t{' '.join((item.help or '').split())}"


def register_powershell_completion() -> None:
    """Register PowerShell completer with click."""

    add_completion_class(PowerShellComplete)
    add_completion_class(PowerShellComplete, "pwsh")
