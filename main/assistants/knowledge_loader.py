"""
Модуль для загрузки и управления базами знаний из Markdown файлов
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

# Путь к папке с базами знаний
KNOWLEDGE_BASE_PATH = Path(__file__).parent / "knowledge_bases"


class MarkdownKnowledgeBase:
    """Класс для работы с размеченным Markdown файлом"""
    
    def __init__(self, file_path: str, subject: str):
        self.file_path = Path(file_path)
        self.subject = subject
        self.content = ""
        self.metadata = {}
        self.sections = {}  # topic_id -> content
        self.all_text = ""  # Весь текст для быстрого поиска
        self.load()
    
    def load(self):
        """Загружает и парсит Markdown файл"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Файл {self.file_path} не найден")
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
        
        self.all_text = self.content.lower()
        self.parse_metadata()
        self.parse_sections()
    
    def parse_metadata(self):
        """Парсит метаданные из начала файла"""
        lines = self.content.split('\n')
        in_metadata = False
        
        for line in lines:
            if line.startswith('---'):
                in_metadata = not in_metadata
                continue
            
            if in_metadata and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Обрабатываем списки
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip() for v in value[1:-1].split(',')]
                
                self.metadata[key] = value
    
    def parse_sections(self):
        """Парсит все секции с тегами [topic: ...] и [subtopic: ...]"""
        # Обновленный паттерн для лучшего захвата содержимого
        pattern = r'##?\s*\[(topic|subtopic):\s*([^\]]+)\]([^#]*)'
        
        matches = re.findall(pattern, self.content, re.DOTALL)
        
        for match in matches:
            section_type = match[0]
            topic_id = match[1].strip()
            content = match[2].strip()
            
            # Очищаем контент от лишних пустых строк
            content = re.sub(r'\n\s*\n', '\n\n', content)
            
            if content:  # Добавляем только непустые секции
                self.sections[topic_id] = {
                    'type': section_type,
                    'content': content,
                    'topic_id': topic_id,
                    'subject': self.subject,
                    'file': self.file_path.name
                }
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Улучшенный поиск релевантных секций"""
        query_lower = query.lower()
        results = []
        
        # Разбиваем запрос на слова и удаляем стоп-слова
        stop_words = {'когда', 'как', 'что', 'это', 'такое', 'почему', 'где', 'зачем'}
        keywords = [w for w in query_lower.split() if w not in stop_words and len(w) > 2]
        
        # Добавляем биграммы (словосочетания)
        bigrams = []
        for i in range(len(keywords) - 1):
            bigrams.append(f"{keywords[i]}_{keywords[i+1]}")
        
        all_search_terms = keywords + bigrams
        
        for topic_id, section in self.sections.items():
            content_lower = section['content'].lower()
            topic_lower = topic_id.lower()
            
            score = 0
            
            # Проверяем каждое слово
            for term in all_search_terms:
                # Больше веса за совпадение в теме
                if term in topic_lower:
                    score += 10
                
                # За совпадение в содержании
                if term in content_lower:
                    # Считаем количество вхождений
                    count = content_lower.count(term)
                    score += min(count, 5)  # Максимум 5 баллов за повторения
                
                # Проверяем на частичное совпадение (например, "нн" в "нн_в_причастиях")
                if len(term) > 2:
                    for word in topic_lower.split('_'):
                        if term in word or word in term:
                            score += 3
            
            # Проверяем, есть ли в контенте ключевые слова из запроса
            # Для коротких терминов (типа "нн") делаем отдельную проверку
            for term in keywords:
                if len(term) <= 3 and term in content_lower:
                    score += 5
            
            if score > 0:
                results.append({
                    'topic_id': topic_id,
                    'type': section['type'],
                    'content': section['content'],
                    'score': score,
                    'subject': self.subject,
                    'file': section.get('file', 'unknown')
                })
        
        # Сортируем по релевантности
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results[:top_k]
    
    def simple_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """Простой поиск по ключевым словам (быстрый)"""
        query_lower = query.lower()
        results = []
        
        for topic_id, section in self.sections.items():
            content_lower = section['content'].lower()
            
            # Проверяем наличие всех слов из запроса
            all_words_found = all(word in content_lower or word in topic_id.lower() 
                                  for word in query_lower.split() if len(word) > 2)
            
            if all_words_found or query_lower in content_lower:
                results.append({
                    'topic_id': topic_id,
                    'content': section['content'],
                    'file': section.get('file', 'unknown')
                })
        
        return results[:top_k]
    
    def get_context_for_prompt(self, query: str, top_k: int = 3) -> str:
        """Формирует контекст для промпта"""
        results = self.search(query, top_k)
        
        if not results:
            # Пробуем простой поиск как fallback
            results = self.simple_search(query, top_k)
            if not results:
                return f"Информация по запросу '{query}' не найдена в базе знаний по {self.subject}."
        
        context_parts = []
        for result in results:
            source_info = f"[Источник: {result.get('file', 'unknown')}]"
            context_parts.append(f"### {result['topic_id']}\n{source_info}\n\n{result['content']}")
        
        return "\n\n---\n\n".join(context_parts)


class KnowledgeBaseManager:
    """Менеджер для работы со всеми базами знаний"""
    
    def __init__(self, base_path: Path = KNOWLEDGE_BASE_PATH):
        self.base_path = base_path
        self.knowledge_bases: Dict[str, List[MarkdownKnowledgeBase]] = {}
        self.load_all()
    
    def load_all(self):
        """Загружает все базы знаний из подпапок"""
        if not self.base_path.exists():
            print(f"Папка {self.base_path} не найдена, создаю...")
            self.base_path.mkdir(parents=True, exist_ok=True)
            return
        
        for subject_dir in self.base_path.iterdir():
            if subject_dir.is_dir():
                self.knowledge_bases[subject_dir.name] = []
                # Ищем все .md файлы в папке предмета
                for md_file in sorted(subject_dir.glob("*.md")):
                    try:
                        kb = MarkdownKnowledgeBase(md_file, subject_dir.name)
                        self.knowledge_bases[subject_dir.name].append(kb)
                    except Exception as e:
                        print(f"  Ошибка загрузки {md_file.name}: {e}")
                
    
    def get_knowledge_base(self, subject: str) -> Optional[List[MarkdownKnowledgeBase]]:
        """Получает все базы знаний по предмету"""
        return self.knowledge_bases.get(subject)
    
    def search_all(self, subject: str, query: str, top_k_per_file: int = 2) -> List[Dict]:
        """Ищет по всем файлам предмета"""
        all_results = []
        kbs = self.get_knowledge_base(subject)
        
        if not kbs:
            return all_results
        
        for kb in kbs:
            results = kb.search(query, top_k_per_file)
            all_results.extend(results)
        
        # Сортируем по релевантности
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return all_results[:top_k_per_file * len(kbs)]
    
    def get_context_for_prompt(self, subject: str, query: str, top_k: int = 3) -> str:
        """Получает контекст для конкретного предмета из всех файлов"""
        kbs = self.get_knowledge_base(subject)
        
        if not kbs:
            return f"База знаний по предмету '{subject}' не найдена."
        
        all_contexts = []
        for kb in kbs:
            context = kb.get_context_for_prompt(query, top_k)
            if context and "не найдена" not in context:
                all_contexts.append(context)
        
        if not all_contexts:
            return f"Информация по запросу '{query}' не найдена в базе знаний по {subject}."
        
        return "\n\n" + "=" * 50 + "\n\n".join(all_contexts)


# Создаем глобальный экземпляр для использования в других модулях
knowledge_manager = KnowledgeBaseManager()