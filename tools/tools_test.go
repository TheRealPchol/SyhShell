package tools

import (
	"reflect"
	"testing"
)

func TestFixSlashes(t *testing.T) {
	cases := []struct {
		in   []string
		want []string
	}{
		{[]string{"Hello", "World\\", "!"}, []string{"Hello", "World !"}},
		{[]string{"a\\", "b\\", "c"}, []string{"a b c"}},
		{[]string{"a\\"}, []string{"a"}},
		{[]string{"a", "b"}, []string{"a", "b"}},
		{[]string{}, []string{}},
		{nil, []string{}},
	}

	for _, c := range cases {
		got := FixSlashes(c.in)
		if !reflect.DeepEqual(got, c.want) {
			t.Errorf("FixSlashes(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
