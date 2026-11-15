from typing import Any

class Parser:
    def __init__(self) -> None:
        pass

    def ParseString(self, string: str) -> dict[str, Any]:
        # Убираем переносы строк
        string = string.replace("\n", "")
        # Разбиваем по точке с запятой и убираем пустые элементы
        lines = [line for line in string.split(';') if line.strip()]
        ret: dict[str, Any] = {}

        for line in lines:
            if "=" not in line:
                continue  # Пропускаем некорректные строки без "="
                
            kw = line.split("=")
            key = kw[0].strip()
            value = "=".join(kw[1:]).strip()

            if key not in ret:
                ret[key] = value
            else:
                # Исправлено: превращаем строку в список, сохраняя её ЦЕЛИКОМ, а не только первую букву
                if not isinstance(ret[key], list):
                    ret[key] = [ret[key]]
                # Исправлено: теперь метод append вызывается со скобками и передает значение
                ret[key].append(value)
        return ret

    def ParseLines(self, lines: list[str]) -> dict[str, Any]:
        # Исправлено: тип list[str] вместо str[list] и добавлен return
        return self.ParseString("\n".join(lines))

