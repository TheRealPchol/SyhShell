package console

import (
	"os"
	"os/exec"
	"slices"
	"strings"
	"fmt"
	"goss/config"
	"goss/tools"
)

func ExecuteCommand(command string) error {
	parts := strings.Fields(command)
	if len(parts) == 0 {
		return nil
	}

	if slices.Contains(config.BuildInCommands, parts[0]) {
		switch parts[0] {
		case "cd":
			if len(parts) < 2 {
				homeDir := config.Homed
				
				return os.Chdir(homeDir)
			}
			return os.Chdir(parts[1])
		case "pwd":
			dir, _ := os.Getwd()
			fmt.Println(dir)
			return nil
		}
		return nil
	} else {
		parts = tools.FixSlashes(parts)
		cmd := exec.Command(parts[0], parts[1:]...)
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}
}

