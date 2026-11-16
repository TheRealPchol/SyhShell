package config

const Prompt string = "[$USER@$HOST]: "

var ExitPhrases = []string{
	".exit",
	".quit",
	"-q",
	"-e",
	"--exit",
	"--quit",
	"--bye",
	"-b",
}



var BuildInCommands = []string{
	"cd",
	"alias",
	"export",
	"pwd",
}
