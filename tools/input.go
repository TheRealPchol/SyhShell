package tools

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// reader создаётся один раз: если делать bufio.NewReader(os.Stdin) при каждом
// вызове, он читает stdin с запасом и при следующем вызове выбросит остаток
// буфера — вставленный из буфера обмена многострочный текст потеряется.
var reader = bufio.NewReader(os.Stdin)

func Input(prompt string) (string, error) {
	fmt.Print(prompt)

	result, err := reader.ReadString('\n')
	if err != nil {
		return "", err
	}

	return strings.TrimSpace(result), nil
}
