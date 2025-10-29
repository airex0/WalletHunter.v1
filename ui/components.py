# ui/components.py (نسخة مؤقتة للاختبار)
import flet as ft

def KPI(label: str, value_control: ft.Control):
    # تم تبسيط الكود بالكامل لإزالة أي استدعاء للألوان
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(label),
                value_control,
            ]
        ),
        padding=10,
        border_radius=8,
        bgcolor="blue", # استخدام لون بسيط جدًا ومباشر
        expand=True
    )

def SystemMonitorGauge(label: str, progress_control: ft.Control, text_control: ft.Control):
    return ft.Column(
        [
            ft.Text(label),
            progress_control,
            text_control
        ]
    )