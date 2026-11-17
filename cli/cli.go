package cli

import (
	"errors"
	"fmt"
	"io"
	"os"
	"slices"
	"strings"

	"goss/config"
	"goss/console"
	"goss/tools"
)

func Cli() {
	for {
		dir, err := os.Getwd()
		
		if err != nil {
			dir = "unknown"
		}
		dir = strings.ReplaceAll(dir, config.Homed, config.Home_syb)
		prompt := strings.ReplaceAll(config.Prompt, "$DIR", dir)
		prompt = strings.ReplaceAll(prompt, "$USER", config.Username.Username)
		prompt = strings.ReplaceAll(prompt, "$HOST", config.Hostname)

		inp, err := tools.Input(prompt)	
		
		inp = strings.ReplaceAll(inp, config.Home_syb, config.Homed)
		inp = strings.ReplaceAll(inp, "$USER", config.Username.Username)
		inp = strings.ReplaceAll(inp, "$HOST", config.Hostname)

		if err != nil {
			if errors.Is(err, io.EOF) {
				fmt.Println()
				return
			}
			fmt.Println("Error: ", err)
			continue
		}

		if slices.Contains(config.ExitPhrases, strings.TrimSpace(inp)) {
			return
		}

		if err := console.ExecuteCommand(inp); err != nil {
			fmt.Println("Error: ", err)
		}
	}
}

