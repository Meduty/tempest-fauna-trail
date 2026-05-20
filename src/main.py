import flet as ft


def main(page: ft.Page):
    page.title = "Tempest Fauna Trail"
    page.window.width = 1024
    page.window.height = 768
    page.add(ft.Text("Tempest Fauna Trail", size=32, weight=ft.FontWeight.BOLD))


if __name__ == "__main__":
    ft.app(target=main)
