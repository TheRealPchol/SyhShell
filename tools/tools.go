package tools

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

func ClearConsole() error {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("cmd", "/c", "cls")
	case "linux", "darwin":
		cmd = exec.Command("clear")
	default:
		fmt.Print("\033[H\033[2J")
		return nil
	}

	cmd.Stdout = os.Stdout
	return cmd.Run()
}

// FixSlashes убирает завершающий обратный слеш у элементов среза.
func FixSlashes(obj []string) []string {
	result := []string{}

	for _, o := range obj {
		if strings.HasSuffix(o, "\\") {
			result = append(result, strings.TrimSuffix(o, "\\"))
		} else {
			result = append(result, o)
		}
	}

	return result
}
