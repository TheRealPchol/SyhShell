package config

import (
	"os"
	"os/user"
)
var Prompt string = "\033[1;32m[$USER@$HOST]\033[0m \033[1;34m$DIR\033[0m: " 

var ExitPhrases = []string{
	".exit",
	".quit",
	"-q",
	"-e",
	"--exit",
	"--quit",
	"--bye",
	"-b",
	".bye",
}



var BuildInCommands = []string{
	"cd",
	"alias",
	"export",
	"pwd",
}

var Homed, _ = os.UserHomeDir()
var Home_syb = "~"

var Hostname, _= os.Hostname()
var Username, _ = user.Current()
