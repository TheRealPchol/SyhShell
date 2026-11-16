package console

import (
	"os"
	"os/exec"
	"strings"
	"slices"
	"fmt"

	"goss/config"
)

func ExecuteCommand(command string) error {
	parts := strings.Fields(command)
	if len(parts) == 0 {
		return nil
	}
	if slices.Contains(config.BuildInCommands, parts[0]) {
		fmt.Println("BuildInCommand")
		return nil
	} else {
		cmd := exec.Command(parts[0], parts[1:]...)
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}

}
