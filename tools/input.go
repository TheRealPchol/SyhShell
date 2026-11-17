package tools

import (
	"github.com/chzyer/readline"
)

func Input(prompt string) (string, error) {
	rl, err := readline.New(prompt)
	if err != nil {
		return "", err
	}
	defer rl.Close()

	for {
		line, err := rl.Readline()
		if err != nil {
			if err == readline.ErrInterrupt {
				continue
			}
			return "", err
		}
		return line, nil
	}
}

