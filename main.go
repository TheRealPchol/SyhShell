package main

import (
	"fmt"
	"goss/tools"
)

func main() {
	fmt.Println("Hello, Go SisyphShell")

	test := []string{"Hello", "World\\", "!"}
	s := tools.FixSlashes(test)
	fmt.Println(s)
}
