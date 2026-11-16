package cli

import (
	"errors"
	"fmt"
	"io"
	"slices"

	"goss/config"
	"goss/console"
	"goss/tools"
)

func Cli() {
	for {
		inp, err := tools.Input(config.Prompt)
		if err != nil {
			if errors.Is(err, io.EOF) {
				fmt.Println()
				return
			}
			fmt.Println("Error: ", err)
			continue
		}

		if slices.Contains(config.ExitPhrases, inp) {
			return
		}

		if err := console.ExecuteCommand(inp); err != nil {
			fmt.Println("Error: ", err)
		}
	}
}
