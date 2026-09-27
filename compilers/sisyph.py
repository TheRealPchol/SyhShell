import os
import sys
from typing import Any

labels: dict = {}
debug: bool = False
libs: dict = {}
call_stack: list = []
dcs = {}
viz_zone = {}
ERROR_CODES = []


def get_args(text: str, start_char: str, end_char: str) -> str:
	start_idx = text.find(start_char)
	end_idx = text.rfind(end_char)

	if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
		return text[start_idx + len(start_char):end_idx]

	return ""


def get_from_dc(data_class: str, key: Any, data_class_storage: dict = dcs) -> Any:
	if data_class in data_class_storage:
		target_dc = data_class_storage[data_class]
		if key in target_dc:
			return target_dc[key]
		else:
			print('Sisyph Error: [ERROR_CODE_57]')
			sys.exit(1)
	else:
		print(f'Sisyph Error: Cannot find data class "{data_class}" in data class storage "{data_class_storage}"')
		sys.exit(1)


def write_to_dc(data_class: str, key: str, value: Any):
	dcs[data_class][key] = value


def remove_from_dc(data_class: str, key: str):
	dcs[data_class].pop(key)


def preprocessing(lines: list[str]) -> list[str]:
	preprocessing_return = []

	for cl in lines:
		if not cl.strip():
			continue

		if ';' in cl:
			parts = cl.split(';')
			preprocessing_return.extend([p for p in parts if p.strip()])
		elif '~~' in cl:
			val = cl.split('~~')[0]
			if val.strip():
				preprocessing_return.append(val)
		else:
			preprocessing_return.append(cl)

	return preprocessing_return


def execute_line(line: str, lines: list, pc: list):
	if debug: print(f"DEBUG exec: '{line.strip()}'")
	line = line.strip()
	if not line:
		return

	if ';' in line:
		for sub in line.split(';'):
			execute_line(sub, lines, pc)
	args_sp: list = line.split(' ')
	args_dot: list = line.split('.')

	# --- INCLUDE ---
	if args_sp[0] == "include":
		filepath = f"{args_sp[1]}.syh"
		if not os.path.isfile(filepath):
			filepath = os.path.join("lib", filepath)
		if os.path.isfile(filepath):
			with open(filepath, 'r', encoding='utf-8') as ffi:
				ffi_lines = ffi.readlines()

			offset = len(lines)
			new_labels = collect_labels(ffi_lines)

			lib_name = os.path.basename(args_sp[1])
			for name, pos in new_labels.items():
				labels[f"{lib_name}.{name}"] = pos + offset

			lines.extend(ffi_lines)
			return
		else:
			libs[os.path.basename(args_sp[1])] = True
			exec(f"{os.path.basename(args_sp[1])} = True", viz_zone)
			return
	# --- GOTO ---
	if args_sp[0] == "goto":
		if len(args_sp) >= 2:
			target = args_sp[1]
			if target == "back":
				if call_stack:
					pc[0] = call_stack.pop()
					if debug: print(f"DEBUG goto back: pc_after={pc[0]}")
				else:
					print("Sisyph Error: Call stack is empty, nowhere to return")
			elif target in labels:
				call_stack.append(pc[0])
				pc[0] = labels[target]
				if debug: print(f"DEBUG goto: pc_after={pc[0]}, stack_depth={len(call_stack)}")
			else:
				print(f"Sisyph Error: Unknown label '{target}'")
		return
	# --- EXIT ---
	if args_sp[0] == "exit":
		exit_code: str = line.split('exit ', 1)[1].strip() if 'exit ' in line else ''
		if exit_code in ('0', 'True', ''):
			print('The program has completed successfully.')
		else:
			print(f'The program terminated with code "{exit_code}"')
		pc[0] = len(lines)
		return
	# --- STDLIB ---
	if libs.get("stdlib") and args_dot[0] == "stdlib":
		method = args_dot[1].split()[0]

		if method == "stdout":
			arg = line.split("stdlib.stdout ", 1)[1]
			exec(f"print({arg})", viz_zone)

		elif method == "stdin":
			if len(args_sp) >= 3:
				var_name = args_sp[1]
				prompt_raw = line.split(f"stdlib.stdin {var_name} ", 1)[1].strip()
				try:
					prompt_val = eval(prompt_raw, viz_zone)
				except Exception:
					prompt_val = prompt_raw
				viz_zone[var_name] = input(prompt_val)
			else:
				prompt_raw = line.split("stdlib.stdin ", 1)[1].strip()
				try:
					prompt_val = eval(prompt_raw, viz_zone)
				except Exception:
					prompt_val = prompt_raw
				input(prompt_val)
		return
	# --- V ---
	if libs.get("v") and args_dot[0] == "v":
		if debug: print(f"DEBUG v: libs={libs}, args_dot={args_dot}")
		method = args_dot[1].split()[0] if len(args_dot) > 1 else ""

		match method:
			case 'int':
				var_name = args_sp[1]
				value_expr = line.split(f"v.int {var_name} ", 1)[1]
				exec(f"{var_name} = int({value_expr})", viz_zone)

			case 'str':
				var_name = args_sp[1]
				value_expr = line.split(f"v.str {var_name} ", 1)[1]
				exec(f"{var_name} = str({value_expr})", viz_zone)

			case 'float':
				var_name = args_sp[1]
				value_expr = line.split(f"v.float {var_name} ", 1)[1]
				exec(f"{var_name} = float({value_expr})", viz_zone)

			case 'bool':
				var_name = args_sp[1]
				value_expr = line.split(f"v.bool {var_name} ", 1)[1]
				exec(f"{var_name} = bool({value_expr})", viz_zone)
			case 'list':
				var_name = args_sp[1]
				value_expr = line.split(f"v.list {var_name} ", 1)[1]
				exec(f"{var_name} = list({value_expr})", viz_zone)
				if debug: print(f"DEBUG list: {var_name} = {viz_zone[var_name]}")
		return
	# --- IF ---
	if args_sp[0] == 'if':
		condition_raw = line.split("if ", 1)[1].split(" then ", 1)[0]
		then_cmd = line.split(" then ", 1)[1]

		exec(f"_sisyph_temp = bool({condition_raw})", viz_zone)
		if viz_zone["_sisyph_temp"]:
			execute_line(then_cmd, lines, pc)
		return
	# --- FILE ---
	if libs.get("file") and args_dot[0] == "file":
		method = args_dot[1].split()[0] if len(args_dot) > 1 else ""

		match method:
			case 'read':
				var_name = args_sp[1]
				filepath = line.split(f"file.read {var_name} ", 1)[1].strip()
				try:
					with open(filepath.strip('"').strip("'"), 'r', encoding='utf-8') as f:
						viz_zone[var_name] = f.read()
				except Exception as e:
					print(f"Sisyph File Error: {e}")
					viz_zone[var_name] = ""

			case 'write':
				filepath = args_sp[1].strip('"').strip("'")
				content_expr = line.split(f"file.write {args_sp[1]} ", 1)[1]
				try:
					content = eval(content_expr, viz_zone)
				except Exception:
					content = content_expr
				with open(filepath, 'w', encoding='utf-8') as f:
					f.write(str(content))

			case 'append':
				filepath = args_sp[1].strip('"').strip("'")
				content_expr = line.split(f"file.append {args_sp[1]} ", 1)[1]
				try:
					content = eval(content_expr, viz_zone)
				except Exception:
					content = content_expr
				with open(filepath, 'a', encoding='utf-8') as f:
					f.write(str(content))

			case 'delete':
				filepath = args_sp[1].strip('"').strip("'")
				try:
					os.remove(filepath)
				except Exception as e:
					print(f"Sisyph File Error: {e}")

			case 'exists':
				var_name = args_sp[1]
				filepath = args_sp[2].strip('"').strip("'")
				viz_zone[var_name] = os.path.isfile(filepath)

			case 'lines':
				var_name = args_sp[1]
				filepath = line.split(f"file.lines {var_name} ", 1)[1].strip()
				try:
					with open(filepath.strip('"').strip("'"), 'r', encoding='utf-8') as f:
						viz_zone[var_name] = f.readlines()
				except Exception as e:
					print(f"Sisyph File Error: {e}")
					viz_zone[var_name] = []
		return
	# --- PYLIB ---
	if libs.get("pylib") and args_dot[0] == "pylib":
		method = args_dot[1].split()[0] if len(args_dot) > 1 else ""

		match method:
			case 'exec':
				code = line.split("pylib.exec ", 1)[1]
				try:
					exec(code, viz_zone)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")

			case 'eval':
				var_name = args_sp[1]
				code = line.split(f"pylib.eval {var_name} ", 1)[1]
				try:
					viz_zone[var_name] = eval(code, viz_zone)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")
					viz_zone[var_name] = None

			case 'import':
				module_name = args_sp[1]
				try:
					exec(f"import {module_name}", viz_zone)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")

			case 'importas':
				module_name = args_sp[1]
				alias = args_sp[2]
				try:
					exec(f"import {module_name} as {alias}", viz_zone)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")

			case 'from':
				code = line.split("pylib.from ", 1)[1]
				try:
					exec(f"from {code}", viz_zone)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")

			case 'get':
				var_name = args_sp[1]
				py_var = args_sp[2]
				try:
					viz_zone[var_name] = viz_zone[py_var]
				except KeyError:
					print(f"Sisyph PyLib Error: Variable '{py_var}' not found")
					viz_zone[var_name] = None

			case 'set':
				py_var = args_sp[1]
				value_expr = line.split(f"pylib.set {py_var} ", 1)[1]
				try:
					viz_zone[py_var] = eval(value_expr, viz_zone)
				except Exception:
					viz_zone[py_var] = value_expr

			case 'print':
				code = line.split("pylib.print ", 1)[1]
				try:
					result = eval(code, viz_zone)
					print(result)
				except Exception as e:
					print(f"Sisyph PyLib Error: {type(e).__name__}: {e}")
		return
	# --- DC ---
	if 'dc' in libs and args_dot[0] == 'dc':
		aof = args_dot[1].split()[0]
		if aof == 'mkdc':
			dcs[args_sp[1]] = {}
		elif aof == 'set':
			boba = line.split('dc.set ')[1]
			dc_name = boba[:boba.find('(')]
			ooo = get_args(boba, '(', ')')
			sata = ooo.split(':: ')
			try:
				value = eval(sata[1].strip(), viz_zone)
			except Exception:
				value = sata[1].strip()
			dcs[dc_name][sata[0].strip()] = value
		elif aof == 'remkey':
			remove_from_dc(args_sp[1], args_sp[2])
		elif aof == 'get':
			var_name = args_sp[1]
			rest = line.split(f"dc.get {var_name} ", 1)[1]
			dc_name = rest[:rest.find('(')]
			ooo = get_args(rest, '(', ')')
			sata = ooo.split(':: ')
			viz_zone[var_name] = get_from_dc(dc_name.strip(), sata[0].strip())
		elif aof == 'move':
			boba = line.split('dc.move ')[1]
			from_paren_open = boba.find('(')
			from_paren_close = boba.find(')')
			from_dc = boba[:from_paren_open].strip()
			from_key = boba[from_paren_open + 1:from_paren_close].strip()
			rest2 = boba[from_paren_close + 1:].strip()
			to_paren_open = rest2.find('(')
			to_paren_close = rest2.find(')')
			to_dc = rest2[:to_paren_open].strip()
			to_key = rest2[to_paren_open + 1:to_paren_close].strip()
			val = get_from_dc(from_dc, from_key)
			write_to_dc(to_dc, to_key, val)
			remove_from_dc(from_dc, from_key)
		elif aof == 'copy':
			boba = line.split('dc.copy ')[1]
			from_paren_open = boba.find('(')
			from_paren_close = boba.find(')')
			from_dc = boba[:from_paren_open].strip()
			from_key = boba[from_paren_open + 1:from_paren_close].strip()
			rest2 = boba[from_paren_close + 1:].strip()
			to_paren_open = rest2.find('(')
			to_paren_close = rest2.find(')')
			to_dc = rest2[:to_paren_open].strip()
			to_key = rest2[to_paren_open + 1:to_paren_close].strip()
			val = get_from_dc(from_dc, from_key)
			write_to_dc(to_dc, to_key, val)
		elif aof == 'copy2var':
			var_name = args_sp[1]
			rest = line.split(f"dc.copy2var {var_name} ", 1)[1]
			dc_name = rest[:rest.find('(')]
			ooo = get_args(rest, '(', ')')
			viz_zone[var_name] = get_from_dc(dc_name.strip(), ooo.strip())
		elif aof == 'move2var':
			var_name = args_sp[1]
			rest = line.split(f"dc.move2var {var_name} ", 1)[1]
			dc_name = rest[:rest.find('(')]
			ooo = get_args(rest, '(', ')')
			viz_zone[var_name] = get_from_dc(dc_name.strip(), ooo.strip())
			remove_from_dc(dc_name.strip(), ooo.strip())
		return


def execute_lines(lines: list):
	lines = preprocessing(lines=lines)

	labels.clear()
	call_stack.clear()
	for i, line in enumerate(lines):
		stripped = line.strip()
		if stripped.startswith('@'):
			label_name = stripped.lstrip('@').strip().split()[0]
			labels[label_name] = i

	pc = [0]
	while pc[0] < len(lines):
		line = lines[pc[0]]
		pc[0] += 1

		if line.strip().startswith('@'):
			continue

		execute_line(line, lines, pc)


def execute_file(filename: str):
	if not os.path.isfile(filename):
		print(f"Sisyph Error: File '{filename}' not found.")
		return

	with open(filename, "r", encoding="utf-8") as fl:
		lines = fl.readlines()

	execute_lines(lines)


def collect_labels(lines: list) -> dict:
	labels = {}
	for i, line in enumerate(lines):
		stripped = line.strip()
		if stripped.startswith('@'):
			label_name = stripped.lstrip('@').strip().split()[0]
			labels[label_name] = i
	return labels


if __name__ == "__main__":
	import traceback
	try:
		execute_file(sys.argv[1])
	except Exception as e:
		traceback.print_exc()