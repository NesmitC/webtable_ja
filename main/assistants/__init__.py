# main/assistants/__init__.py
"""
Модули Нейро-команды
"""

from .teacher_russian import TeacherRussian
from .analyst import Analyst
from .methodist import Methodist
from .marketing import Marketing

__all__ = ['TeacherRussian', 'Analyst', 'Methodist', 'Marketing']