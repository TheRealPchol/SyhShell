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

// FixSlashes склеивает элементы среза: если элемент оканчивается на "\",
// он считается продолжением и объединяется со следующим через пробел.
//
//	{"Hello", "World\\", "!"} -> {"Hello", "World !"}
//	{"a\\", "b\\", "c"}       -> {"a b c"}
//	{"a\\"}                   -> {"a"}
func FixSlashes(obj []string) []string {
	result := []string{}
	current := ""
	building := false

	for _, o := range obj {
		continues := strings.HasSuffix(o, "\\")
		piece := strings.TrimSuffix(o, "\\")

		if building {
			current += " " + piece
		} else {
			current = piece
		}

		if continues {
			building = true
			continue
		}

		result = append(result, current)
		building = false
	}

	// Последний элемент оканчивался на "\", склеивать больше не с чем —
	// отдаём накопленное как есть, без висящего слеша.
	if building {
		result = append(result, current)
	}

	return result
}

func UpdateString(target *string, newValue string) {
	if target != nil { // Проверка на nil, чтобы избежать паники
		*target = newValue
	}
}
