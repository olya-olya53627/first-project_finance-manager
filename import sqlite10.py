import sqlite3
import csv
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import calendar
from contextlib import contextmanager
import os
import glob
import math

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.modalview import ModalView
from kivy.uix.recycleview import RecycleView
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty, BooleanProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, Triangle
from typing import Callable
from kivy.event import EventDispatcher

# Классы базы данных
class DatabaseManager:
    """Класс для управления базой данных"""
    
    def __init__(self, db_name: str = 'finance.db'):
        self.db_name = db_name
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для работы с БД"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # создание таблицы категорий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense'))
                )
            ''')
            
            # создание таблицы операций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    category_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            ''')
            
            # Базовые категории
            default_categories = [
                ('Зарплата', 'income'),
                ('Инвестиции', 'income'),
                ('Продукты', 'expense'),
                ('Транспорт', 'expense'),
                ('Жилье', 'expense'),
                ('Развлечения', 'expense'),
                ('Здоровье', 'expense'),
                ('Одежда', 'expense'),
                ('Образование', 'expense')
            ]
            
            for name, type_ in default_categories:
                cursor.execute(
                    "INSERT OR IGNORE INTO categories (name, type) VALUES (?, ?)",
                    (name, type_)
                )
            
            conn.commit()
    
    def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        """Метод выполнения запросов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            if fetch:
                return cursor.fetchall()
    
    def fetch_all(self, query: str, params: tuple = ()):
        """Получение всех записей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def fetch_one(self, query: str, params: tuple = ()):
        """Получение одной записи"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()


class FinanceManager:
    """Класс для управления финансовым менеджером"""
    
    def __init__(self, db_name: str = 'finance.db'):
        self.db = DatabaseManager(db_name)
    
    def add_category(self, name: str, type_: str) -> bool:
        """Добавление новой категории"""
        # Конвертируем русские значения в английские
        type_mapping = {
            'доход': 'income',
            'расход': 'expense',
            'income': 'income',
            'expense': 'expense'
        }
        
        if type_ not in type_mapping:
            return False
        
        db_type = type_mapping[type_]
        
        try:
            self.db.execute_query(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                (name, db_type)
            )
            return True
        except sqlite3.IntegrityError:
            return False
    
    def edit_category(self, old_name: str, new_name: Optional[str] = None, new_type: Optional[str] = None) -> bool:
        """Редактирование существующей категории"""
        category = self.db.fetch_one(
            "SELECT id, type FROM categories WHERE name = ?",
            (old_name,)
        )
        
        if not category:
            return False
        
        category_id, current_type = category
        
        if new_name is None or new_name == "":
            new_name = old_name
        if new_type is None or new_type == "":
            new_type = current_type

        # Конвертируем тип, если нужно
        type_mapping = {
            'доход': 'income',
            'расход': 'expense',
            'income': 'income',
            'expense': 'expense'
        }
        
        if new_type not in type_mapping:
            return False
        
        db_new_type = type_mapping[new_type]
        
        if new_name != old_name:
            existing = self.db.fetch_one(
                "SELECT id FROM categories WHERE name = ?",
                (new_name,)
            )
            if existing:
                return False
        
        try:
            self.db.execute_query(
                "UPDATE categories SET name = ?, type = ? WHERE id = ?",
                (new_name, db_new_type, category_id)
            )    
            return True
        except Exception:
            return False
    
    def get_category_stats(self, name: str) -> Optional[Dict]:
        """Получение статистики по категории"""
        category = self.db.fetch_one(
            "SELECT id, type FROM categories WHERE name = ?",
            (name,)
        )
        
        if not category:
            return None
        
        category_id, category_type = category
        
        stats = self.db.fetch_one(
            "SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM transactions WHERE category_id = ?",
            (category_id,)
        )
        
        if not stats:
            return {
                'type': category_type,
                'count': 0,
                'total': 0.0,
                'last_transaction': None
            }
        
        count, total = stats
        
        last_transaction = None
        if count > 0:
            last_tx = self.db.fetch_one(
                "SELECT date, amount, description FROM transactions WHERE category_id = ? ORDER BY date DESC, id DESC LIMIT 1",
                (category_id,)
            )
            if last_tx:
                last_transaction = last_tx
        
        return {
            'type': category_type,
            'count': count,
            'total': total,
            'last_transaction': last_transaction
        }
    
    def delete_category(self, name: str, force: bool = False) -> bool:
        """Удаление категории"""
        category = self.db.fetch_one(
            "SELECT id, type FROM categories WHERE name = ?",
            (name,)
        )
        
        if not category:
            print(f"❌ Категория '{name}' не найдена")
            return False
        
        category_id, category_type = category
        
        transactions_count = self.db.fetch_one(
            "SELECT COUNT(*) FROM transactions WHERE category_id = ?",
            (category_id,)
        )[0]

        if transactions_count > 0 and not force:
            return False

        try:
            if transactions_count > 0:
                self.db.execute_query(
                    "DELETE FROM transactions WHERE category_id = ?",
                    (category_id,)
                )

            self.db.execute_query(
                "DELETE FROM categories WHERE id = ?",
                (category_id,)
            )

            return True
        except Exception as e:
            print(f"❌ Ошибка при удалении категории: {e}")
            return False
    
    def add_transaction(self, date: str, category_name: str, amount: float,
                       description: str = "", type_: str = 'expense') -> bool:
        """Добавление новой операции"""
        
        category = self.db.fetch_one(
            "SELECT id, type FROM categories WHERE name = ?",
            (category_name,)
        )
        
        if not category:
            return False
        
        category_id, category_type = category
        
        if category_type != type_:
            return False
        
        try:
            self.db.execute_query('''
                INSERT INTO transactions (date, category_id, amount, description, type)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, category_id, amount, description, type_))
            return True
        except Exception:
            return False
    
    def get_month_summary(self, year: int, month: int) -> Dict:
        """Получение сводки за месяц"""
        
        last_day = calendar.monthrange(year, month)[1]
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{last_day}"
        
        total_income = self.db.fetch_one('''
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'income' AND date BETWEEN ? AND ?
        ''', (start_date, end_date))[0]
        
        total_expense = self.db.fetch_one('''
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'expense' AND date BETWEEN ? AND ?
        ''', (start_date, end_date))[0]
        
        expenses_by_category = dict(self.db.fetch_all('''
            SELECT c.name, COALESCE(SUM(t.amount), 0)
            FROM categories c
            LEFT JOIN transactions t ON c.id = t.category_id 
                AND t.type = 'expense' 
                AND t.date BETWEEN ? AND ?
            WHERE c.type = 'expense'
            GROUP BY c.name
            HAVING COALESCE(SUM(t.amount), 0) > 0
            ORDER BY COALESCE(SUM(t.amount), 0) DESC
        ''', (start_date, end_date)))
        
        income_by_category = dict(self.db.fetch_all('''
            SELECT c.name, COALESCE(SUM(t.amount), 0)
            FROM categories c
            LEFT JOIN transactions t ON c.id = t.category_id 
                AND t.type = 'income' 
                AND t.date BETWEEN ? AND ?
            WHERE c.type = 'income'
            GROUP BY c.name
            HAVING COALESCE(SUM(t.amount), 0) > 0
            ORDER BY COALESCE(SUM(t.amount), 0) DESC
        ''', (start_date, end_date)))
        
        recent_transactions = self.db.fetch_all('''
            SELECT t.date, c.name, t.amount, t.type, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.date BETWEEN ? AND ?
            ORDER BY t.date DESC
            LIMIT 10
        ''', (start_date, end_date))
        
        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': total_income - total_expense,
            'expenses_by_category': expenses_by_category,
            'income_by_category': income_by_category,
            'recent_transactions': recent_transactions,
            'month': f"{year}-{month:02d}"
        }
    
    def export_to_csv(self, year: int, month: int, filename: str = None):
        """Экспорт данных за месяц в CSV"""
        if not filename:
            filename = f'finance_{year}_{month:02d}.csv'
        
        summary = self.get_month_summary(year, month)
        
        last_day = calendar.monthrange(year, month)[1]
        transactions = self.db.fetch_all('''
            SELECT t.date, c.name, t.amount, t.type, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.date BETWEEN ? AND ?
            ORDER BY t.date
        ''', (f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day}"))
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow([f'Сводка за {summary["month"]}'])
            writer.writerow([f'Доходы: {summary["total_income"]:.2f} руб.'])
            writer.writerow([f'Расходы: {summary["total_expense"]:.2f} руб.'])
            writer.writerow([f'Баланс: {summary["balance"]:.2f} руб.'])
            writer.writerow([])
            
            writer.writerow(['Дата', 'Категория', 'Сумма', 'Тип', 'Описание'])
            for transaction in transactions:
                writer.writerow(transaction)
            
            writer.writerow([])
            
            if summary['expenses_by_category']:
                writer.writerow(['Расходы по категориям:'])
                for category, amount in summary['expenses_by_category'].items():
                    writer.writerow([category, f'{amount:.2f} руб.'])
        
        return filename
    
    def get_csv_files(self):
        """Получение списка CSV файлов в текущей директории"""
        csv_files = glob.glob('*.csv')
        csv_files.sort(key=os.path.getmtime, reverse=True)  # Сортировка по дате изменения
        return csv_files
    
    def read_csv_file(self, filename: str):
        """Чтение CSV файла и возврат его содержимого"""
        if not os.path.exists(filename):
            return None
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            print(f"Ошибка при чтении файла {filename}: {e}")
            return None
    
    def delete_csv_file(self, filename: str):
        """Удаление CSV файла"""
        try:
            if os.path.exists(filename):
                os.remove(filename)
                return True
            return False
        except Exception as e:
            print(f"Ошибка при удалении файла {filename}: {e}")
            return False
    
    def get_all_categories(self) -> List[Tuple]:
        """Получение всех категорий"""
        categories = self.db.fetch_all(
            "SELECT name, type FROM categories ORDER BY type, name"
        )
        # Конвертируем обратно для отображения
        type_mapping = {
            'income': 'доход',
            'expense': 'расход'
        }
        
        result = []
        for name, type_ in categories:
            result.append((name, type_mapping.get(type_, type_)))
        return result
    
    def get_recent_transactions(self, limit: int = 20):
        """Получение последних операций"""
        return self.db.fetch_all('''
            SELECT t.date, c.name, t.amount, t.type, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
        ''', (limit,))
    
    def get_all_transactions(self):
        """Получение всех операций"""
        return self.db.fetch_all('''
            SELECT t.date, c.name, t.amount, t.type, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            ORDER BY t.date DESC, t.id DESC
        ''')
    
    def get_transactions_by_date(self, date: str):
        """Получение операций по конкретной дате"""
        return self.db.fetch_all('''
            SELECT t.date, c.name, t.amount, t.type, t.description
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.date = ?
            ORDER BY t.id DESC
        ''', (date,))
    
    def get_category_data_for_charts(self, year: int, month: int):
        """Получение данных для диаграмм по категориям"""
        summary = self.get_month_summary(year, month)
        
        return {
            'income_data': summary['income_by_category'],
            'expense_data': summary['expenses_by_category'],
            'total_income': summary['total_income'],
            'total_expense': summary['total_expense'],
            'balance': summary['balance']
        }


# Классы для диаграмм
class PieChartWidget(BoxLayout):
    """Виджет для отображения круговой диаграммы"""
    
    def __init__(self, data: Dict[str, float] = None, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.data = data if data else {}
        self.title = title
        self.size_hint = (1, 1)
        self.padding = 10
        self.colors = [
            (0.2, 0.6, 0.8, 1),   # Синий
            (0.9, 0.3, 0.3, 1),   # Красный
            (0.2, 0.8, 0.4, 1),   # Зеленый
            (0.9, 0.8, 0.2, 1),   # Желтый
            (0.8, 0.2, 0.8, 1),   # Фиолетовый
            (0.2, 0.8, 0.8, 1),   # Голубой
            (0.9, 0.6, 0.2, 1),   # Оранжевый
            (0.6, 0.2, 0.2, 1),   # Коричневый
            (0.3, 0.3, 0.9, 1),   # Темно-синий
            (0.8, 0.8, 0.8, 1),   # Серый
        ]
        self.bind(size=self._update_canvas, pos=self._update_canvas)
        
        # Контейнер для диаграммы и заголовка
        self.container = BoxLayout(orientation='vertical', size_hint=(1, 1))
        
        # Заголовок
        self.title_label = Label(
            text=title,
            size_hint=(1, 0.1),
            font_size='16sp',
            bold=True
        )
        self.container.add_widget(self.title_label)
        
        # Область для рисования диаграммы
        self.chart_area = BoxLayout(size_hint=(1, 0.9))
        self.container.add_widget(self.chart_area)
        
        self.add_widget(self.container)
        
        self._update_canvas()
    
    def _update_canvas(self, *args):
        """Обновление отображения диаграммы"""
        self.chart_area.canvas.clear()
        
        if not self.data:
            with self.chart_area.canvas:
                Color(0.9, 0.9, 0.9, 1)
                Rectangle(pos=self.chart_area.pos, size=self.chart_area.size)
            
            # Добавляем текст "Нет данных"
            self.chart_area.clear_widgets()
            no_data_label = Label(
                text="Нет данных для отображения",
                size_hint=(1, 1),
                color=(0.5, 0.5, 0.5, 1),
                font_size='14sp'
            )
            self.chart_area.add_widget(no_data_label)
            return
        
        # Рассчитываем общую сумму
        total = sum(self.data.values())
        if total <= 0:
            return
        
        # Рассчитываем центр и радиус
        center_x = self.chart_area.center_x
        center_y = self.chart_area.center_y
        radius = min(self.chart_area.width, self.chart_area.height) * 0.35
        
        # Очищаем старые виджеты
        self.chart_area.clear_widgets()
        
        # Рисуем круговую диаграмму
        with self.chart_area.canvas:
            # Фон
            Color(0.95, 0.95, 0.95, 1)
            Ellipse(pos=(center_x - radius, center_y - radius), 
                   size=(radius * 2, radius * 2))
            
            # Секторы диаграммы
            start_angle = 0
            color_index = 0
            
            for i, (category, value) in enumerate(self.data.items()):
                if value <= 0:
                    continue
                    
                # Вычисляем угол сектора
                angle = (value / total) * 360
                
                # Выбираем цвет
                color = self.colors[color_index % len(self.colors)]
                color_index += 1
                
                # Рисуем сектор
                Color(*color)
                self._draw_pie_sector(center_x, center_y, radius, 
                                     start_angle, start_angle + angle)
                
                # Обновляем начальный угол для следующего сектора
                start_angle += angle
            
            # Центральный круг (для эффекта пончика)
            Color(1, 1, 1, 1)
            Ellipse(pos=(center_x - radius * 0.4, center_y - radius * 0.4), 
                   size=(radius * 0.8, radius * 0.8))
            
            # Текст в центре
            Color(0.2, 0.2, 0.2, 1)
            total_text = f"{total:.0f}₽"
    
    def _draw_pie_sector(self, cx, cy, radius, start_angle, end_angle):
        """Рисование сектора круговой диаграммы"""
        # Конвертируем углы в радианы
        start_rad = math.radians(start_angle - 90)  # Начинаем с верха
        end_rad = math.radians(end_angle - 90)
        
        # Координаты центра
        points = [(cx, cy)]
        
        # Добавляем точки по окружности
        steps = max(2, int((end_angle - start_angle) / 2))  # Количество шагов
        for i in range(steps + 1):
            angle = start_rad + (end_rad - start_rad) * (i / steps)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append((x, y))
        
        # Рисуем треугольники для сектора
        for i in range(1, len(points) - 1):
            Triangle(points=[points[0][0], points[0][1],
                            points[i][0], points[i][1],
                            points[i+1][0], points[i+1][1]])

    def update_data(self, new_data: Dict[str, float], title: str = None):
        """Обновление данных диаграммы"""
        self.data = new_data
        if title:
            self.title = title
            self.title_label.text = title
        self._update_canvas()


class ChartPopup(Popup):
    """Всплывающее окно с диаграммами"""
    
    def __init__(self, finance_manager, year: int, month: int, chart_type: str = "all", **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.year = year
        self.month = month
        self.chart_type = chart_type
        
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        month_name = month_names[month - 1]
        
        self.title = f"Диаграммы за {month_name} {year}"
        self.size_hint = (0.95, 0.95)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Заголовок
        title_label = Label(
            text=f"📊 Диаграммы за {month_name} {year}",
            size_hint=(1, 0.08),
            font_size='20sp',
            bold=True
        )
        layout.add_widget(title_label)
        
        # Получаем данные
        chart_data = self.finance_manager.get_category_data_for_charts(year, month)
        
        if chart_type == "all":
            # Показываем все диаграммы
            charts_container = BoxLayout(orientation='horizontal', size_hint=(1, 0.8), spacing=20)
            
            # Диаграмма доходов
            if chart_data['income_data']:
                income_chart = PieChartWidget(
                    data=chart_data['income_data'],
                    title="📈 Доходы",
                    size_hint=(0.5, 1)
                )
                charts_container.add_widget(income_chart)
            else:
                no_income = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
                no_income.add_widget(Label(
                    text="📈 Доходы",
                    size_hint=(1, 0.1),
                    font_size='16sp',
                    bold=True
                ))
                no_income.add_widget(Label(
                    text="Нет данных",
                    size_hint=(1, 0.9),
                    color=(0.5, 0.5, 0.5, 1)
                ))
                charts_container.add_widget(no_income)
            
            # Диаграмма расходов
            if chart_data['expense_data']:
                expense_chart = PieChartWidget(
                    data=chart_data['expense_data'],
                    title="📉 Расходы",
                    size_hint=(0.5, 1)
                )
                charts_container.add_widget(expense_chart)
            else:
                no_expense = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
                no_expense.add_widget(Label(
                    text="📉 Расходы",
                    size_hint=(1, 0.1),
                    font_size='16sp',
                    bold=True
                ))
                no_expense.add_widget(Label(
                    text="Нет данных",
                    size_hint=(1, 0.9),
                    color=(0.5, 0.5, 0.5, 1)
                ))
                charts_container.add_widget(no_expense)
            
            layout.add_widget(charts_container)
            
        elif chart_type == "income":
            # Только диаграмма доходов
            if chart_data['income_data']:
                income_chart = PieChartWidget(
                    data=chart_data['income_data'],
                    title=f"📈 Доходы за {month_name} {year}",
                    size_hint=(1, 0.8)
                )
                layout.add_widget(income_chart)
            else:
                layout.add_widget(Label(
                    text="Нет данных о доходах за этот период",
                    size_hint=(1, 0.8),
                    color=(0.5, 0.5, 0.5, 1),
                    font_size='18sp'
                ))
                
        elif chart_type == "expense":
            # Только диаграмма расходов
            if chart_data['expense_data']:
                expense_chart = PieChartWidget(
                    data=chart_data['expense_data'],
                    title=f"📉 Расходы за {month_name} {year}",
                    size_hint=(1, 0.8)
                )
                layout.add_widget(expense_chart)
            else:
                layout.add_widget(Label(
                    text="Нет данных о расходах за этот период",
                    size_hint=(1, 0.8),
                    color=(0.5, 0.5, 0.5, 1),
                    font_size='18sp'
                ))
        
        # Статистика
        stats_text = (
            f"💰 Общий доход: {chart_data['total_income']:.2f} руб.\n"
            f"💸 Общие расходы: {chart_data['total_expense']:.2f} руб.\n"
            f"📊 Баланс: {chart_data['balance']:.2f} руб."
        )
        
        stats_label = Label(
            text=stats_text,
            size_hint=(1, 0.12),
            font_size='16sp',
            bold=True
        )
        layout.add_widget(stats_label)
        
        # Легенда
        if chart_type == "income" and chart_data['income_data']:
            legend = self._create_legend(chart_data['income_data'], "Доходы по категориям:")
        elif chart_type == "expense" and chart_data['expense_data']:
            legend = self._create_legend(chart_data['expense_data'], "Расходы по категориям:")
        elif chart_type == "all":
            # Объединенная легенда
            all_data = {**chart_data['income_data'], **chart_data['expense_data']}
            if all_data:
                legend = self._create_legend(all_data, "Все категории:")
            else:
                legend = Label(text="Нет данных по категориям", size_hint=(1, 0.1))
        else:
            legend = Label(text="Нет данных", size_hint=(1, 0.1))
        
        legend_scroll = ScrollView(size_hint=(1, 0.2))
        legend_scroll.add_widget(legend)
        layout.add_widget(legend_scroll)
        
        # Кнопка закрытия
        btn_close = Button(text="Закрыть", size_hint=(1, 0.08))
        btn_close.bind(on_press=self.dismiss)
        layout.add_widget(btn_close)
        
        self.content = layout
    
    def _create_legend(self, data: Dict[str, float], title: str):
        """Создание легенды для диаграммы"""
        colors = [
            (0.2, 0.6, 0.8, 1),   # Синий
            (0.9, 0.3, 0.3, 1),   # Красный
            (0.2, 0.8, 0.4, 1),   # Зеленый
            (0.9, 0.8, 0.2, 1),   # Желтый
            (0.8, 0.2, 0.8, 1),   # Фиолетовый
            (0.2, 0.8, 0.8, 1),   # Голубой
            (0.9, 0.6, 0.2, 1),   # Оранжевый
            (0.6, 0.2, 0.2, 1),   # Коричневый
            (0.3, 0.3, 0.9, 1),   # Темно-синий
            (0.8, 0.8, 0.8, 1),   # Серый
        ]
        
        total = sum(data.values())
        
        legend_layout = GridLayout(cols=2, size_hint_y=None, spacing=5, padding=5)
        legend_layout.bind(minimum_height=legend_layout.setter('height'))
        
        # Заголовок легенды
        title_label = Label(
            text=title,
            size_hint_y=None,
            height=40,
            font_size='16sp',
            bold=True,
            color=(0.2, 0.2, 0.2, 1)
        )
        legend_layout.add_widget(title_label)
        legend_layout.add_widget(Label(text="", size_hint_y=None, height=40))
        
        # Элементы легенды
        for i, (category, value) in enumerate(data.items()):
            # Цветной квадрат
            color_box = BoxLayout(size_hint_y=None, height=30)
            with color_box.canvas:
                Color(*colors[i % len(colors)])
                Rectangle(pos=color_box.pos, size=(25, 25))
            legend_layout.add_widget(color_box)
            
            # Текст категории
            percentage = (value / total) * 100 if total > 0 else 0
            legend_text = f"{category}: {value:.2f} руб. ({percentage:.1f}%)"
            legend_item = Label(
                text=legend_text,
                size_hint_y=None,
                height=30,
                halign='left',
                text_size=(300, None)
            )
            legend_layout.add_widget(legend_item)
        
        legend_layout.height = len(legend_layout.children) * 35
        return legend_layout


# Kivy GUI Классы
class MessagePopup(Popup):
    """Всплывающее окно для сообщений"""
    def __init__(self, title="Сообщение", message="", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.8, 0.4)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text=message, halign='center'))
        
        btn = Button(text='OK', size_hint=(1, 0.3))
        btn.bind(on_press=self.dismiss)
        layout.add_widget(btn)
        
        self.content = layout


class ConfirmPopup(Popup):
    """Всплывающее окно подтверждения"""
    def __init__(self, title="Подтверждение", message="", callback=None, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.size_hint = (0.8, 0.4)
        self.callback = callback
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text=message, halign='center'))
        
        btn_layout = BoxLayout(size_hint=(1, 0.3), spacing=10)
        btn_yes = Button(text='Да')
        btn_no = Button(text='Нет')
        
        btn_yes.bind(on_press=self.on_yes)
        btn_no.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_yes)
        btn_layout.add_widget(btn_no)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def on_yes(self, instance):
        if self.callback:
            self.callback()
        self.dismiss()


class CalendarTab(BoxLayout):
    """Вкладка с финансовым календарем"""
    def __init__(self, finance_manager, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.orientation = 'vertical'
        self.padding = [10, 10]
        self.spacing = 10
        
        # Заголовок
        header = BoxLayout(size_hint=(1, 0.1), spacing=10)
        header.add_widget(Label(
            text="Финансовый календарь",
            size_hint=(0.5, 1),
            font_size='24sp',
            bold=True,
            color=(0.5, 0.5, 0.95, 0.95)
        ))
        
        btn_today = Button(text='Сегодня', size_hint=(0.1, 0.8))
        btn_today.bind(on_press=self.go_to_today)
        header.add_widget(btn_today)
        
        self.add_widget(header)
        
        # Выбор месяца
        now = datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        
        month_layout = BoxLayout(size_hint=(1, 0.08), spacing=10)
        
        btn_prev = Button(text='<-', size_hint=(0.1, 1))
        btn_prev.bind(on_press=self.prev_month)
        
        self.month_label = Label(
            text=f"{self.get_month_name(self.current_month)} {self.current_year}",
            size_hint=(0.8, 1),
            font_size='18sp',
            bold=True
        )
        
        btn_next = Button(text='->', size_hint=(0.1, 1))
        btn_next.bind(on_press=self.next_month)
        
        month_layout.add_widget(btn_prev)
        month_layout.add_widget(self.month_label)
        month_layout.add_widget(btn_next)
        
        self.add_widget(month_layout)
        
        # Календарь
        self.calendar_grid = GridLayout(cols=7, size_hint=(1, 0.5), spacing=2)
        self.add_widget(self.calendar_grid)
        
        # Операции за выбранный день
        self.selected_date = None
        self.day_transactions_label = Label(
            text="Выберите день в календаре",
            size_hint=(1, 0.2),
            halign='left',
            valign='top'
        )
        self.day_transactions_label.bind(size=self.day_transactions_label.setter('text_size'))
        
        scroll = ScrollView(size_hint=(1, 0.2))
        scroll.add_widget(self.day_transactions_label)
        self.add_widget(scroll)
        
        # Обновляем календарь
        self.update_calendar()
    
    def get_month_name(self, month: int) -> str:
        """Получение названия месяца"""
        months = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return months[month - 1]
    
    def update_calendar(self):
        """Обновление календаря"""
        self.calendar_grid.clear_widgets()
        
        # Заголовки дней недели
        days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        for day in days:
            self.calendar_grid.add_widget(Label(
                text=day,
                bold=True,
                color=(0.4, 0.4, 0.4, 1),
                size_hint_y=None,
                height=30
            ))
        
        # Получаем первый день месяца и количество дней
        first_weekday, days_in_month = calendar.monthrange(self.current_year, self.current_month)
        
        # Пустые ячейки перед первым днем
        for _ in range(first_weekday):
            self.calendar_grid.add_widget(Label(text="", size_hint_y=None, height=50))
        
        # Дни месяца
        for day in range(1, days_in_month + 1):
            date_str = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
            
            # Получаем операции за день
            transactions = self.finance_manager.get_transactions_by_date(date_str)
            
            # Создаем кнопку дня
            btn = Button(
                text=str(day),
                size_hint_y=None,
                height=50,
                background_normal='',
                background_color=self.get_day_color(transactions),
                font_size='14sp'
            )
            
            # Показываем сумму операций
            if transactions:
                total = sum(t[2] for t in transactions)
                btn.text = f"{day}\n{total:.0f}₽"
                btn.font_size = '12sp'
            
            # Выделяем выбранный день
            if date_str == self.selected_date:
                btn.background_color = (0.2, 0.6, 0.8, 1)
                btn.color = (0.2, 0.2, 0.2, 1)
            
            # Выделяем сегодняшний день
            today = datetime.now().strftime("%Y-%m-%d")
            if date_str == today:
                btn.border = [2, 2, 2, 2]
                btn.background_color = (btn.background_color[0] + 0.1, 
                                      btn.background_color[1] + 0.1, 
                                      btn.background_color[2] + 0.1, 1)
            
            btn.bind(on_press=lambda instance, d=date_str: self.show_day_transactions(d))
            
            self.calendar_grid.add_widget(btn)
    
    def get_day_color(self, transactions):
        """Получение цвета дня в зависимости от операций"""
        if not transactions:
            return (0.95, 0.95, 0.95, 1)  # Серый - нет операций
        
        total_income = sum(t[2] for t in transactions if t[3] == 'income')
        total_expense = sum(t[2] for t in transactions if t[3] == 'expense')
        balance = total_income - total_expense
        
        if balance > 0:
            return (0.2, 0.8, 0.4, 1)  # Зеленый - положительный баланс
        elif balance < 0:
            return (0.9, 0.3, 0.3, 1)  # Красный - отрицательный баланс
        else:
            return (0.9, 0.9, 1, 1)  # Синий - баланс нулевой
    
    def show_day_transactions(self, date: str):
        """Показать операции за день"""
        self.selected_date = date
        transactions = self.finance_manager.get_transactions_by_date(date)
        
        if not transactions:
            self.day_transactions_label.text = f"📅 {date}\n\nНет операций за этот день"
            self.update_calendar()
            return
        
        text = f"📅 {date}\n\n"
        total_income = sum(t[2] for t in transactions if t[3] == 'income')
        total_expense = sum(t[2] for t in transactions if t[3] == 'expense')
        balance = total_income - total_expense
        
        text += f"💵 Доходы: {total_income:.2f} руб.\n"
        text += f"💸 Расходы: {total_expense:.2f} руб.\n"
        text += f"💰 Баланс: {balance:.2f} руб.\n\n"
        
        text += "Операции:\n"
        for date_, category, amount, type_, description in transactions:
            type_symbol = "➕" if type_ == 'income' else "➖"
            desc = description if description else "-"
            text += f"{type_symbol} {category}: {amount:.2f} руб.\n"
            if description and description != "-":
                text += f"   📝 {desc}\n"
        
        self.day_transactions_label.text = text
        self.update_calendar()
    
    def prev_month(self, instance):
        """Предыдущий месяц"""
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.month_label.text = f"{self.get_month_name(self.current_month)} {self.current_year}"
        self.selected_date = None
        self.day_transactions_label.text = "Выберите день в календаре"
        self.update_calendar()
    
    def next_month(self, instance):
        """Следующий месяц"""
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.month_label.text = f"{self.get_month_name(self.current_month)} {self.current_year}"
        self.selected_date = None
        self.day_transactions_label.text = "Выберите день в календаре"
        self.update_calendar()
    
    def go_to_today(self, instance):
        """Переход к сегодняшнему дню"""
        now = datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self.month_label.text = f"{self.get_month_name(self.current_month)} {self.current_year}"
        today = now.strftime("%Y-%m-%d")
        self.show_day_transactions(today)
    
    def add_income_today(self, instance):
        """Быстрое добавление дохода на сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.show_add_transaction(today, 'доход')
    
    def add_expense_today(self, instance):
        """Быстрое добавление расхода на сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.show_add_transaction(today, 'расход')
    
    def show_add_transaction(self, date: str, type_: str):
        """Показать окно добавления транзакции"""
        def callback():
            self.update_calendar()
            if date == self.selected_date:
                self.show_day_transactions(date)
            # Уведомляем приложение об обновлении
            if self.app_instance:
                self.app_instance.refresh_all_tabs()
        
        popup = AddTransactionPopup(self.finance_manager, app_instance=self.app_instance, callback=callback)
        popup.date_input.text = date
        popup.type_spinner.text = type_
        popup.open()


class AddTransactionPopup(Popup):
    """Окно добавления транзакции"""
    def __init__(self, finance_manager, app_instance=None, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.callback = callback
        self.title = "Добавить операцию"
        self.size_hint = (0.9, 0.8)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        layout.add_widget(Label(text="Тип операции:", size_hint=(1, 0.1)))
        self.type_spinner = Spinner(
            text='расход',
            values=('доход', 'расход'),
            size_hint=(1, 0.1)
        )
        layout.add_widget(self.type_spinner)
        
        layout.add_widget(Label(text="Дата (ГГГГ-ММ-ДД):", size_hint=(1, 0.1)))
        self.date_input = TextInput(
            text=datetime.now().strftime("%Y-%m-%d"),
            size_hint=(1, 0.1),
            multiline=False
        )
        layout.add_widget(self.date_input)
        
        # Категория
        layout.add_widget(Label(text="Категория:", size_hint=(1, 0.1)))
        self.category_spinner = Spinner(text='', size_hint=(1, 0.1))
        layout.add_widget(self.category_spinner)
        
        # Привязываем обновление списка категорий при изменении типа операции
        self.type_spinner.bind(text=self.update_categories)
        self.update_categories()
        
        # Сумма
        layout.add_widget(Label(text="Сумма:", size_hint=(1, 0.1)))
        self.amount_input = TextInput(
            text='',
            size_hint=(1, 0.1),
            multiline=False,
            input_filter='float'
        )
        layout.add_widget(self.amount_input)
        
        # Описание
        layout.add_widget(Label(text="Описание:", size_hint=(1, 0.1)))
        self.description_input = TextInput(
            text='',
            size_hint=(1, 0.2),
            multiline=True
        )
        layout.add_widget(self.description_input)
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        btn_add = Button(text='Добавить')
        btn_cancel = Button(text='Отмена')
        
        btn_add.bind(on_press=self.add_transaction)
        btn_cancel.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_add)
        btn_layout.add_widget(btn_cancel)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def update_categories(self, *args):
        """Обновление списка категорий"""
        categories = self.finance_manager.get_all_categories()
        current_type = self.type_spinner.text
        
        # Конвертируем русский тип в английский для фильтрации
        type_mapping = {
            'доход': 'income',
            'расход': 'expense'
        }
        
        if current_type in type_mapping:
            db_type = type_mapping[current_type]
            filtered_cats = [c[0] for c in categories if c[1] == current_type]
        else:
            filtered_cats = [c[0] for c in categories if c[1] == current_type]
        
        if filtered_cats:
            self.category_spinner.values = filtered_cats
            self.category_spinner.text = filtered_cats[0]
        else:
            self.category_spinner.values = ['Нет категорий']
            self.category_spinner.text = 'Нет категорий'
    
    def add_transaction(self, instance):
        """Добавление транзакции"""
        try:
            date = self.date_input.text
            category = self.category_spinner.text
            amount = float(self.amount_input.text)
            description = self.description_input.text
            type_text = self.type_spinner.text
            
            # Конвертируем русский тип в английский
            type_mapping = {
                'доход': 'income',
                'расход': 'expense'
            }
            
            if type_text not in type_mapping:
                MessagePopup(title="Ошибка", message="Неверный тип операции!").open()
                return
            
            type_ = type_mapping[type_text]
            
            if not date or not category or category == 'Нет категорий':
                MessagePopup(title="Ошибка", message="Заполните все поля!").open()
                return
            
            if amount <= 0:
                MessagePopup(title="Ошибка", message="Сумма должна быть положительной!").open()
                return
            
            success = self.finance_manager.add_transaction(
                date, category, amount, description, type_
            )
            
            if success:
                MessagePopup(title="Успех", message="Операция добавлена!").open()
                
                # Вызываем callback для обновления календаря
                if self.callback:
                    self.callback()
                
                # Обновляем все вкладки через приложение
                if self.app_instance:
                    Clock.schedule_once(lambda dt: self.app_instance.refresh_all_tabs(), 0.1)
                
                self.dismiss()
            else:
                MessagePopup(title="Ошибка", message="Не удалось добавить операцию!").open()
        except ValueError:
            MessagePopup(title="Ошибка", message="Некорректная сумма!").open()


class AddCategoryPopup(Popup):
    """Окно добавления категории"""
    def __init__(self, finance_manager, app_instance=None, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.callback = callback
        self.title = "Добавить категорию"
        self.size_hint = (0.8, 0.5)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Название
        layout.add_widget(Label(text="Название категории:", size_hint=(1, 0.2)))
        self.name_input = TextInput(
            text='',
            size_hint=(1, 0.2),
            multiline=False
        )
        layout.add_widget(self.name_input)
        
        # Тип
        layout.add_widget(Label(text="Тип категории:", size_hint=(1, 0.2)))
        self.type_spinner = Spinner(
            text='расход',
            values=('расход', 'доход'),
            size_hint=(1, 0.2)
        )
        layout.add_widget(self.type_spinner)
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.3), spacing=10)
        btn_add = Button(text='Добавить')
        btn_cancel = Button(text='Отмена')
        
        btn_add.bind(on_press=self.add_category)
        btn_cancel.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_add)
        btn_layout.add_widget(btn_cancel)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def add_category(self, instance):
        """Добавление категории"""
        name = self.name_input.text.strip()
        type_ = self.type_spinner.text
        
        if not name:
            MessagePopup(title="Ошибка", message="Введите название категории!").open()
            return
        
        success = self.finance_manager.add_category(name, type_)
        
        if success:
            MessagePopup(title="Успех", message=f"Категория '{name}' добавлена!").open()
            
            # Локальный callback
            if self.callback:
                self.callback()
            
            # Обновляем все вкладки
            if self.app_instance:
                Clock.schedule_once(lambda dt: self.app_instance.refresh_all_tabs(), 0.1)
            
            self.dismiss()
        else:
            MessagePopup(title="Ошибка", message=f"Категория '{name}' уже существует!").open()


class EditCategoryPopup(Popup):
    """Окно редактирования категории"""
    def __init__(self, finance_manager, category_name, app_instance=None, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.old_name = category_name
        self.app_instance = app_instance
        self.callback = callback
        self.title = f"Редактировать категорию: {category_name}"
        self.size_hint = (0.8, 0.6)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Старое название
        layout.add_widget(Label(text=f"Текущее название: {category_name}", size_hint=(1, 0.1)))
        
        # Новое название
        layout.add_widget(Label(text="Новое название:", size_hint=(1, 0.1)))
        self.name_input = TextInput(
            text=category_name,
            size_hint=(1, 0.1),
            multiline=False
        )
        layout.add_widget(self.name_input)
        
        # Тип
        layout.add_widget(Label(text="Тип категории:", size_hint=(1, 0.1)))
        self.type_spinner = Spinner(
            text='расход',
            values=('расход', 'доход'),
            size_hint=(1, 0.1)
        )
        layout.add_widget(self.type_spinner)
        
        # Получаем текущий тип категории
        categories = finance_manager.get_all_categories()
        for cat_name, cat_type in categories:
            if cat_name == category_name:
                self.type_spinner.text = cat_type
                break
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        btn_save = Button(text='Сохранить')
        btn_cancel = Button(text='Отмена')
        
        btn_save.bind(on_press=self.save_category)
        btn_cancel.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_save)
        btn_layout.add_widget(btn_cancel)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def save_category(self, instance):
        """Сохранение изменений категории"""
        new_name = self.name_input.text.strip()
        new_type = self.type_spinner.text
        
        if not new_name:
            MessagePopup(title="Ошибка", message="Введите название категории!").open()
            return
        
        success = self.finance_manager.edit_category(self.old_name, new_name, new_type)
        
        if success:
            MessagePopup(title="Успех", message=f"Категория '{self.old_name}' обновлена!").open()
            
            # Локальный callback
            if self.callback:
                self.callback()
            
            # Обновляем все вкладки
            if self.app_instance:
                Clock.schedule_once(lambda dt: self.app_instance.refresh_all_tabs(), 0.1)
            
            self.dismiss()
        else:
            MessagePopup(title="Ошибка", message="Не удалось обновить категорию!").open()


class DeleteCategoryPopup(Popup):
    """Окно удаления категории"""
    def __init__(self, finance_manager, category_name, app_instance=None, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.category_name = category_name
        self.app_instance = app_instance
        self.callback = callback
        self.title = f"Удалить категорию: {category_name}"
        self.size_hint = (0.8, 0.5)
        
        self.stats = finance_manager.get_category_stats(category_name)

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Статистика категории
        if self.stats:
            message = f"Категория: {category_name}\n"
            # Конвертируем тип для отображения
            type_text = "доход" if self.stats['type'] == 'income' else "расход"
            message += f"Тип: {type_text}\n"
            message += f"Операций: {self.stats['count']}\n"
            message += f"Общая сумма: {self.stats['total']:.2f} руб."
        else:
            message = f"Категория: {category_name}\n(без операций)"
        
        layout.add_widget(Label(text=message, size_hint=(1, 0.4)))
        
        if self.stats and self.stats['count'] > 0:
            layout.add_widget(Label(text="Вариант удаления:", size_hint=(1, 0.1)))
            self.method_spinner = Spinner(
                text='Без операций',
                values=('Без операций', 'С операциями'),
                size_hint=(1, 0.1)
            )
            layout.add_widget(self.method_spinner)
        else:
            # Если операций нет, скрываем выбор
            self.method_spinner = None
            layout.add_widget(Label(text="Категория пуста", size_hint=(1, 0.1)))
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        btn_delete = Button(text='Удалить')
        btn_cancel = Button(text='Отмена')
        
        btn_delete.bind(on_press=self.delete_category)
        btn_cancel.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_delete)
        btn_layout.add_widget(btn_cancel)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def delete_category(self, instance):
        """Удаление категории"""
        if self.method_spinner:
            force = self.method_spinner.text == 'С операциями'
        else:
            force = False

        def confirm_delete():
            success = self.finance_manager.delete_category(self.category_name, force)
            
            if success:
                MessagePopup(title="Успех", message=f"Категория '{self.category_name}' удалена!").open()
                
                # Локальный callback
                if self.callback:
                    self.callback()
                
                # Обновляем все вкладки
                if self.app_instance:
                    Clock.schedule_once(lambda dt: self.app_instance.refresh_all_tabs(), 0.1)
                
                self.dismiss()
            else:
                error_msg = "Не удалось удалить категорию!\n"
                if self.stats and self.stats['count'] > 0 and not force:
                    error_msg += "Выберите 'С операциями' или убедитесь, что категория пуста."
                else:
                    error_msg += "Возможно, категория не существует или произошла ошибка базы данных."
                MessagePopup(title="Ошибка", message=error_msg).open()

        if force and self.stats and self.stats['count'] > 0:
            ConfirmPopup(
                title="Подтверждение",
                message=f"Удалить {self.stats['count']} операций категории '{self.category_name}'?",
                callback=confirm_delete
            ).open()
        else:
            # Если операций нет или выбран "Без операций", но операции есть
            if self.stats and self.stats['count'] > 0 and not force:
                MessagePopup(
                    title="Ошибка", 
                    message=f"Категория содержит {self.stats['count']} операций.\nВыберите 'С операциями' или удалите операции вручную."
                ).open()
            else:
                confirm_delete()


class MonthSummaryPopup(Popup):
    """Окно сводки за месяц"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.title = "Сводка за месяц"
        self.size_hint = (0.9, 0.8)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Выбор месяца и года
        control_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        control_layout.add_widget(Label(text="Год:", size_hint=(0.2, 1)))
        
        self.year_input = TextInput(
            text=str(datetime.now().year),
            size_hint=(0.3, 1),
            multiline=False,
            input_filter='int'
        )
        control_layout.add_widget(self.year_input)
        
        control_layout.add_widget(Label(text="Месяц:", size_hint=(0.2, 1)))
        
        self.month_input = TextInput(
            text=str(datetime.now().month),
            size_hint=(0.3, 1),
            multiline=False,
            input_filter='int'
        )
        control_layout.add_widget(self.month_input)
        
        layout.add_widget(control_layout)
        
        # Кнопка показа
        btn_show = Button(text="Показать сводку", size_hint=(1, 0.1))
        btn_show.bind(on_press=self.show_summary)
        layout.add_widget(btn_show)
        
        # Поле для отображения сводки
        self.summary_label = Label(
            text="Выберите месяц и нажмите 'Показать сводку'",
            size_hint=(1, 0.7),
            halign='left',
            valign='top'
        )
        self.summary_label.bind(size=self.summary_label.setter('text_size'))
        
        scroll = ScrollView(size_hint=(1, 0.7))
        scroll.add_widget(self.summary_label)
        layout.add_widget(scroll)
        
        # Кнопка закрытия
        btn_close = Button(text="Закрыть", size_hint=(1, 0.1))
        btn_close.bind(on_press=self.dismiss)
        layout.add_widget(btn_close)
        
        self.content = layout
    
    def show_summary(self, instance):
        """Показать сводку за месяц"""
        try:
            year = int(self.year_input.text)
            month = int(self.month_input.text)
            
            if month < 1 or month > 12:
                MessagePopup(title="Ошибка", message="Месяц должен быть от 1 до 12!").open()
                return
            
            summary = self.finance_manager.get_month_summary(year, month)
            
            text = f"📅 Сводка за {summary['month']}:\n\n"
            text += f"💵 Доходы: {summary['total_income']:.2f} руб.\n"
            text += f"💸 Расходы: {summary['total_expense']:.2f} руб.\n"
            text += f"💰 Баланс: {summary['balance']:.2f} руб.\n\n"
            
            if summary['expenses_by_category']:
                text += "📈 Расходы по категориям:\n"
                for category, amount in summary['expenses_by_category'].items():
                    text += f"  - {category}: {amount:.2f} руб.\n"
                text += "\n"
            else:
                text += "📈 Нет расходов за этот период\n\n"
                
            if summary['income_by_category']:
                text += "📥 Доходы по категориям:\n"
                for category, amount in summary['income_by_category'].items():
                    text += f"  - {category}: {amount:.2f} руб.\n"
            else:
                text += "📥 Нет доходов за этот период\n"
            
            self.summary_label.text = text
            
        except ValueError:
            MessagePopup(title="Ошибка", message="Введите корректные значения года и месяца!").open()


class ViewCSVFilesPopup(Popup):
    """Окно просмотра CSV файлов"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.title = "Просмотр CSV файлов"
        self.size_hint = (0.9, 0.9)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Заголовок
        header = BoxLayout(size_hint=(1, 0.1), spacing=10)
        header.add_widget(Label(
            text="Экспортированные CSV файлы:",
            size_hint=(0.8, 1),
            font_size='16sp',
            bold=True
        ))
        
        btn_refresh = Button(text='Обновить', size_hint=(0.2, 1))
        btn_refresh.bind(on_press=self.refresh_files)
        header.add_widget(btn_refresh)
        
        layout.add_widget(header)
        
        # Список файлов
        self.files_list = GridLayout(cols=1, size_hint=(1, 0.3), spacing=5)
        self.files_list.bind(minimum_height=self.files_list.setter('height'))
        
        files_scroll = ScrollView(size_hint=(1, 0.3))
        files_scroll.add_widget(self.files_list)
        layout.add_widget(files_scroll)
        
        # Поле для отображения содержимого файла
        self.content_label = Label(
            text="Выберите файл для просмотра",
            size_hint=(1, 0.6),
            halign='left',
            valign='top'
        )
        self.content_label.bind(size=self.content_label.setter('text_size'))
        
        content_scroll = ScrollView(size_hint=(1, 0.6))
        content_scroll.add_widget(self.content_label)
        layout.add_widget(content_scroll)
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        btn_close = Button(text='Закрыть')
        btn_delete = Button(text='Удалить выбранный')
        
        btn_close.bind(on_press=self.dismiss)
        btn_delete.bind(on_press=self.delete_selected_file)
        
        btn_layout.add_widget(btn_close)
        btn_layout.add_widget(btn_delete)
        layout.add_widget(btn_layout)
        
        self.content = layout
        
        # Текущий выбранный файл
        self.selected_file = None
        
        # Загружаем список файлов
        self.refresh_files()
    
    def refresh_files(self, instance=None):
        """Обновление списка файлов"""
        # Очищаем старый список
        self.files_list.clear_widgets()
        
        # Получаем список CSV файлов
        csv_files = self.finance_manager.get_csv_files()
        
        if not csv_files:
            no_files_label = Label(
                text="Нет экспортированных CSV файлов",
                size_hint_y=None,
                height=40,
                color=(0.5, 0.5, 0.5, 1)
            )
            self.files_list.add_widget(no_files_label)
            self.selected_file = None
            return
        
        # Добавляем файлы в список
        for filename in csv_files:
            try:
                # Получаем информацию о файле
                file_size = os.path.getsize(filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filename))
                
                # Создаем кнопку для файла
                btn = Button(
                    text=f"{filename} ({file_size/1024:.1f} КБ, {file_time.strftime('%d.%m.%Y %H:%M')})",
                    size_hint_y=None,
                    height=50,
                    background_normal='',
                    background_color=(0.8, 0.9, 1, 1) if filename != self.selected_file else (0.6, 0.8, 1, 1)
                )
                
                # Привязываем обработчик
                btn.bind(on_press=lambda instance, f=filename: self.select_file(f, instance))
                
                self.files_list.add_widget(btn)
            except Exception as e:
                print(f"Ошибка при обработке файла {filename}: {e}")
    
    def select_file(self, filename, button):
        """Выбор файла для просмотра"""
        # Сбрасываем цвет всех кнопок
        for child in self.files_list.children:
            if isinstance(child, Button):
                child.background_color = (0.8, 0.9, 1, 1)
        
        # Выделяем выбранную кнопку
        button.background_color = (0.6, 0.8, 1, 1)
        
        # Сохраняем выбранный файл
        self.selected_file = filename
        
        # Читаем и отображаем содержимое файла
        content = self.finance_manager.read_csv_file(filename)
        if content:
            self.content_label.text = content
        else:
            self.content_label.text = f"Не удалось прочитать файл: {filename}"
    
    def delete_selected_file(self, instance):
        """Удаление выбранного файла"""
        if not self.selected_file:
            MessagePopup(title="Ошибка", message="Выберите файл для удаления!").open()
            return
        
        ConfirmPopup(
            title="Подтверждение удаления",
            message=f"Вы уверены, что хотите удалить файл:\n{self.selected_file}?",
            callback=self.perform_delete
        ).open()
    
    def perform_delete(self):
        """Выполнение удаления файла"""
        if self.finance_manager.delete_csv_file(self.selected_file):
            MessagePopup(title="Успех", message=f"Файл '{self.selected_file}' удален!").open()
            self.selected_file = None
            self.content_label.text = "Выберите файл для просмотра"
            self.refresh_files()
        else:
            MessagePopup(title="Ошибка", message=f"Не удалось удалить файл '{self.selected_file}'!").open()


class ExportCSVPopup(Popup):
    """Окно экспорта в CSV"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.title = "Экспорт в CSV"
        self.size_hint = (0.8, 0.6)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Выбор месяца и года
        control_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        control_layout.add_widget(Label(text="Год:", size_hint=(0.3, 1)))
        
        self.year_input = TextInput(
            text=str(datetime.now().year),
            size_hint=(0.7, 1),
            multiline=False,
            input_filter='int'
        )
        control_layout.add_widget(self.year_input)
        
        layout.add_widget(control_layout)
        
        control_layout2 = BoxLayout(size_hint=(1, 0.2), spacing=10)
        control_layout2.add_widget(Label(text="Месяц:", size_hint=(0.3, 1)))
        
        self.month_input = TextInput(
            text=str(datetime.now().month),
            size_hint=(0.7, 1),
            multiline=False,
            input_filter='int'
        )
        control_layout2.add_widget(self.month_input)
        
        layout.add_widget(control_layout2)
        
        # Имя файла
        control_layout3 = BoxLayout(size_hint=(1, 0.2), spacing=10)
        control_layout3.add_widget(Label(text="Имя файла:", size_hint=(0.3, 1)))
        
        self.filename_input = TextInput(
            text=f'finance_{datetime.now().year}_{datetime.now().month:02d}.csv',
            size_hint=(0.7, 1),
            multiline=False
        )
        control_layout3.add_widget(self.filename_input)
        
        layout.add_widget(control_layout3)
        
        # Информация
        info_label = Label(
            text="Файл будет сохранен в текущей директории.\nПосле экспорта можно просмотреть его в разделе 'Просмотр CSV'.",
            size_hint=(1, 0.2),
            halign='center',
            color=(0.3, 0.3, 0.3, 1)
        )
        layout.add_widget(info_label)
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.2), spacing=10)
        btn_export = Button(text='Экспорт')
        btn_cancel = Button(text='Отмена')
        
        btn_export.bind(on_press=self.export_csv)
        btn_cancel.bind(on_press=self.dismiss)
        
        btn_layout.add_widget(btn_export)
        btn_layout.add_widget(btn_cancel)
        layout.add_widget(btn_layout)
        
        self.content = layout
    
    def export_csv(self, instance):
        """Экспорт в CSV"""
        try:
            year = int(self.year_input.text)
            month = int(self.month_input.text)
            filename = self.filename_input.text.strip()
            
            if month < 1 or month > 12:
                MessagePopup(title="Ошибка", message="Месяц должен быть от 1 до 12!").open()
                return
            
            if not filename:
                filename = f'finance_{year}_{month:02d}.csv'
            
            # Проверяем расширение файла
            if not filename.lower().endswith('.csv'):
                filename += '.csv'
            
            # Проверяем, существует ли файл
            if os.path.exists(filename):
                ConfirmPopup(
                    title="Файл уже существует",
                    message=f"Файл '{filename}' уже существует.\nПерезаписать?",
                    callback=lambda: self.perform_export(year, month, filename)
                ).open()
            else:
                self.perform_export(year, month, filename)
            
        except ValueError:
            MessagePopup(title="Ошибка", message="Введите корректные значения!").open()
    
    def perform_export(self, year: int, month: int, filename: str):
        """Выполнение экспорта"""
        try:
            result = self.finance_manager.export_to_csv(year, month, filename)
            
            MessagePopup(
                title="Успех", 
                message=f"Данные экспортированы в файл:\n{result}\n\nФайл сохранен в: {os.path.abspath(result)}"
            ).open()
            
            self.dismiss()
        except Exception as e:
            MessagePopup(
                title="Ошибка", 
                message=f"Не удалось экспортировать данные:\n{str(e)}"
            ).open()


class CategoriesTab(BoxLayout):
    """Вкладка управления категориями"""
    def __init__(self, finance_manager, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Заголовок
        self.add_widget(Label(
            text="Управление категориями",
            size_hint=(1, 0.1),
            font_size='25sp'
        ))
        
        # Список категорий
        self.categories_label = Label(
            text="",
            size_hint=(2, 2),
            halign='left',
            valign='top'
        )
        self.categories_label.bind(size=self.categories_label.setter('text_size'))
        
        scroll = ScrollView(size_hint=(2, 0.8))
        scroll.add_widget(self.categories_label)
        self.add_widget(scroll)
        
        # Кнопки управления
        btn_layout = GridLayout(cols=4, size_hint=(0.7, 0.1), spacing=10)
        
        btn_add = Button(text='Добавить')
        btn_edit = Button(text='Редактировать')
        btn_delete = Button(text='Удалить')
        btn_refresh = Button(text='Обновить')
        
        btn_add.bind(on_press=self.show_add_category)
        btn_edit.bind(on_press=self.show_edit_category)
        btn_delete.bind(on_press=self.show_delete_category)
        btn_refresh.bind(on_press=self.refresh_categories)
        
        btn_layout.add_widget(btn_add)
        btn_layout.add_widget(btn_edit)
        btn_layout.add_widget(btn_delete)
        btn_layout.add_widget(btn_refresh)
        
        self.add_widget(btn_layout)
        
        # Обновляем список категорий при инициализации
        self.refresh_categories()
    
    def refresh_categories(self, instance=None):
        """Обновление списка категорий"""
        categories = self.finance_manager.get_all_categories()
        
        text = "📥 Доходы:\n"
        income_cats = [c[0] for c in categories if c[1] == 'доход']
        if income_cats:
            for cat in income_cats:
                text += f"  • {cat}\n"
        else:
            text += "  Нет категорий\n"
        
        text += "\n📤 Расходы:\n"
        expense_cats = [c[0] for c in categories if c[1] == 'расход']
        if expense_cats:
            for cat in expense_cats:
                text += f"  • {cat}\n"
        else:
            text += "  Нет категорий\n"
        
        self.categories_label.text = text
    
    def show_add_category(self, instance):
        """Показать окно добавления категории"""
        popup = AddCategoryPopup(self.finance_manager, app_instance=self.app_instance, callback=self.refresh_categories)
        popup.open()
    
    def show_edit_category(self, instance):
        """Показать окно редактирования категории"""
        categories = self.finance_manager.get_all_categories()
        if not categories:
            MessagePopup(title="Ошибка", message="Нет категорий для редактирования!").open()
            return
        
        # Создаем выпадающий список категорий
        dropdown = DropDown()
        for cat_name, cat_type in categories:
            btn = Button(text=cat_name, size_hint_y=None, height=44)
            btn.bind(on_release=lambda btn: self.open_edit_category(btn.text, dropdown))
            dropdown.add_widget(btn)
        
        main_button = Button(text='Выберите категорию', size_hint=(1, 1))
        main_button.bind(on_release=dropdown.open)
        dropdown.bind(on_select=lambda instance, x: setattr(main_button, 'text', x))
        
        popup = Popup(title='Выберите категорию для редактирования', 
                     content=main_button, 
                     size_hint=(0.8, 0.6))
        popup.open()
    
    def open_edit_category(self, category_name, dropdown):
        """Открыть окно редактирования выбранной категории"""
        dropdown.dismiss()
        popup = EditCategoryPopup(self.finance_manager, category_name, 
                                 app_instance=self.app_instance, 
                                 callback=self.refresh_categories)
        popup.open()
    
    def show_delete_category(self, instance):
        """Показать окно удаления категории"""
        categories = self.finance_manager.get_all_categories()
        if not categories:
            MessagePopup(title="Ошибка", message="Нет категорий для удаления!").open()
            return
        
        # Создаем выпадающий список категорий
        dropdown = DropDown()
        for cat_name, cat_type in categories:
            btn = Button(text=cat_name, size_hint_y=None, height=44)
            btn.bind(on_release=lambda btn: self.open_delete_category(btn.text, dropdown))
            dropdown.add_widget(btn)
        
        main_button = Button(text='Выберите категорию', size_hint=(1, 1))
        main_button.bind(on_release=dropdown.open)
        dropdown.bind(on_select=lambda instance, x: setattr(main_button, 'text', x))
        
        popup = Popup(title='Выберите категорию для удаления', 
                     content=main_button, 
                     size_hint=(0.8, 0.6))
        popup.open()
    
    def open_delete_category(self, category_name, dropdown):
        """Открыть окно удаления выбранной категории"""
        dropdown.dismiss()
        popup = DeleteCategoryPopup(self.finance_manager, category_name, 
                                   app_instance=self.app_instance, 
                                   callback=self.refresh_categories)
        popup.open()


class TransactionsTab(BoxLayout):
    """Вкладка операций"""
    def __init__(self, finance_manager, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Регистрируемся как слушатель изменений
        if app_instance:
            app_instance.add_data_listener(self.refresh_transactions)
        
        # Заголовок
        self.add_widget(Label(
            text="Операции",
            size_hint=(1, 0.1),
            font_size='20sp'
        ))
        
        # Кнопки управления
        btn_layout = BoxLayout(size_hint=(1, 0.1), spacing=10)
        btn_add = Button(text='Добавить операцию')
        btn_refresh = Button(text='Обновить')
        
        btn_add.bind(on_press=self.show_add_transaction)
        btn_refresh.bind(on_press=self.refresh_transactions)
        
        btn_layout.add_widget(btn_add)
        btn_layout.add_widget(btn_refresh)
        self.add_widget(btn_layout)
        
        # Таблица транзакций
        self.transactions_grid = GridLayout(cols=5, size_hint=(1, 0.8), spacing=5)
        self.transactions_grid.bind(minimum_height=self.transactions_grid.setter('height'))
        
        # Заголовки столбцов
        headers = ['Дата', 'Категория', 'Сумма', 'Тип', 'Описание']
        for header in headers:
            self.transactions_grid.add_widget(Label(
                text=header,
                size_hint_y=None,
                height=40,
                bold=True
            ))
        
        scroll = ScrollView(size_hint=(1, 0.8))
        scroll.add_widget(self.transactions_grid)
        self.add_widget(scroll)
        
        # Обновляем список транзакций при инициализации
        self.refresh_transactions()
    
    def refresh_transactions(self, instance=None):
        """Обновление списка транзакций"""
        # Очищаем старые данные (кроме заголовков)
        while len(self.transactions_grid.children) > 5:
            self.transactions_grid.remove_widget(self.transactions_grid.children[0])
        
        # Получаем все транзакции
        transactions = self.finance_manager.get_all_transactions()
        
        if not transactions:
            # Добавляем сообщение об отсутствии транзакций
            for i in range(5):
                self.transactions_grid.add_widget(Label(
                    text='Нет операций' if i == 2 else '',
                    size_hint_y=None,
                    height=40
                ))
            return
        
        # Добавляем транзакции
        for date, category, amount, type_, description in transactions:
            # Дата
            self.transactions_grid.add_widget(Label(
                text=date,
                size_hint_y=None,
                height=40
            ))
            
            # Категория
            self.transactions_grid.add_widget(Label(
                text=category,
                size_hint_y=None,
                height=40
            ))
            
            # Сумма
            self.transactions_grid.add_widget(Label(
                text=f"{amount:.2f}",
                size_hint_y=None,
                height=40,
                color=(0, 1, 0, 1) if type_ == 'income' else (1, 0, 0, 1)
            ))
            
            # Тип (конвертируем для отображения)
            type_text = "Доход" if type_ == 'income' else "Расход"
            self.transactions_grid.add_widget(Label(
                text=type_text,
                size_hint_y=None,
                height=40,
                color=(0, 1, 0, 1) if type_ == 'income' else (1, 0, 0, 1)
            ))
            
            # Описание
            desc = description if description else "-"
            self.transactions_grid.add_widget(Label(
                text=desc[:20] + "..." if len(desc) > 20 else desc,
                size_hint_y=None,
                height=40
            ))
    
    def show_add_transaction(self, instance):
        """Показать окно добавления транзакции"""
        def callback():
            self.refresh_transactions()
            # Уведомляем приложение об изменении данных
            if self.app_instance:
                self.app_instance.refresh_all_tabs()
        
        popup = AddTransactionPopup(self.finance_manager, app_instance=self.app_instance, callback=callback)
        popup.open()


class ReportsTab(BoxLayout):
    """Вкладка отчетов с диаграммами"""
    def __init__(self, finance_manager, app_instance=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.app_instance = app_instance
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Регистрируемся как слушатель изменений
        if app_instance:
            app_instance.add_data_listener(self.refresh_reports)
        
        # Заголовок
        self.add_widget(Label(
            text="📈 Отчеты и анализ",
            size_hint=(1, 0.1),
            font_size='24sp',
            bold=True
        ))
        
        # Кнопки отчетов
        btn_layout = GridLayout(cols=4, rows=2, size_hint=(1, 0.25), spacing=10, padding=10)
        
        btn_summary = Button(text='📊 Сводка за месяц')
        btn_export = Button(text='💾 Экспорт в CSV')
        btn_view_csv = Button(text='📂 Просмотр CSV')
        btn_recent = Button(text='🔄 Последние операции')
        
        btn_income_chart = Button(text='📈 Диаграмма доходов')
        btn_expense_chart = Button(text='📉 Диаграмма расходов')
        btn_balance_chart = Button(text='💰 Сравнение')
        btn_all_charts = Button(text='📊 Все диаграммы')
        
        btn_summary.bind(on_press=self.show_summary)
        btn_export.bind(on_press=self.show_export)
        btn_view_csv.bind(on_press=self.show_csv_files)
        btn_recent.bind(on_press=self.show_recent)
        
        btn_income_chart.bind(on_press=self.show_income_chart)
        btn_expense_chart.bind(on_press=self.show_expense_chart)
        btn_balance_chart.bind(on_press=self.show_balance_chart)
        btn_all_charts.bind(on_press=self.show_all_charts)
        
        btn_layout.add_widget(btn_summary)
        btn_layout.add_widget(btn_export)
        btn_layout.add_widget(btn_view_csv)
        btn_layout.add_widget(btn_recent)
        btn_layout.add_widget(btn_income_chart)
        btn_layout.add_widget(btn_expense_chart)
        btn_layout.add_widget(btn_balance_chart)
        btn_layout.add_widget(btn_all_charts)
        
        self.add_widget(btn_layout)
        
        # Диаграммы
        charts_container = BoxLayout(orientation='horizontal', size_hint=(1, 0.65), spacing=20, padding=10)
        
        # Левая диаграмма - доходы
        self.income_chart = PieChartWidget(
            title="📈 Доходы по категориям",
            size_hint=(0.5, 1)
        )
        charts_container.add_widget(self.income_chart)
        
        # Правая диаграмма - расходы
        self.expense_chart = PieChartWidget(
            title="📉 Расходы по категориям",
            size_hint=(0.5, 1)
        )
        charts_container.add_widget(self.expense_chart)
        
        self.add_widget(charts_container)
        
        # Обновляем диаграммы при инициализации
        Clock.schedule_once(lambda dt: self.refresh_charts(), 0.5)
    
    def refresh_charts(self):
        """Обновление диаграмм"""
        try:
            now = datetime.now()
            chart_data = self.finance_manager.get_category_data_for_charts(now.year, now.month)
            
            # Обновляем диаграмму доходов
            if chart_data['income_data']:
                self.income_chart.update_data(chart_data['income_data'], f"📈 Доходы ({now.month:02d}.{now.year})")
            else:
                self.income_chart.update_data({"Нет данных": 1}, "📈 Нет доходов")
            
            # Обновляем диаграмму расходов
            if chart_data['expense_data']:
                self.expense_chart.update_data(chart_data['expense_data'], f"📉 Расходы ({now.month:02d}.{now.year})")
            else:
                self.expense_chart.update_data({"Нет данных": 1}, "📉 Нет расходов")
                
        except Exception as e:
            print(f"Ошибка при обновлении диаграмм: {e}")
    
    def show_summary(self, instance):
        """Показать сводку за месяц"""
        popup = MonthSummaryPopup(self.finance_manager)
        popup.open()
    
    def show_export(self, instance):
        """Показать окно экспорта"""
        popup = ExportCSVPopup(self.finance_manager)
        popup.open()
    
    def show_csv_files(self, instance):
        """Показать окно с CSV файлами"""
        popup = ViewCSVFilesPopup(self.finance_manager)
        popup.open()
    
    def refresh_reports(self):
        """Обновление данных в отчетах"""
        self.refresh_charts()
        self.show_recent(None)
    
    def show_recent(self, instance):
        """Показать последние операции в отдельном окне"""
        transactions = self.finance_manager.get_recent_transactions(30)
        
        popup = Popup(title="Последние операции", size_hint=(0.9, 0.9))
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        if not transactions:
            layout.add_widget(Label(text="📭 Нет операций", font_size='18sp'))
        else:
            # Создаем таблицу
            table = GridLayout(cols=5, size_hint_y=None, spacing=5)
            table.bind(minimum_height=table.setter('height'))
            
            # Заголовки
            headers = ['Дата', 'Категория', 'Сумма', 'Тип', 'Описание']
            for header in headers:
                table.add_widget(Label(
                    text=header,
                    size_hint_y=None,
                    height=40,
                    bold=True,
                    color=(0.2, 0.2, 0.2, 1)
                ))
            
            # Данные
            for date, category, amount, type_, description in transactions:
                # Дата
                table.add_widget(Label(
                    text=date,
                    size_hint_y=None,
                    height=35
                ))
                
                # Категория
                table.add_widget(Label(
                    text=category,
                    size_hint_y=None,
                    height=35
                ))
                
                # Сумма
                table.add_widget(Label(
                    text=f"{amount:.2f}",
                    size_hint_y=None,
                    height=35,
                    color=(0, 0.8, 0, 1) if type_ == 'income' else (0.8, 0, 0, 1)
                ))
                
                # Тип
                type_text = "Доход" if type_ == 'income' else "Расход"
                table.add_widget(Label(
                    text=type_text,
                    size_hint_y=None,
                    height=35,
                    color=(0, 0.8, 0, 1) if type_ == 'income' else (0.8, 0, 0, 1)
                ))
                
                # Описание
                desc = description if description else "-"
                table.add_widget(Label(
                    text=desc[:15] + "..." if len(desc) > 15 else desc,
                    size_hint_y=None,
                    height=35
                ))
            
            table.height = (len(transactions) + 1) * 40
            
            scroll = ScrollView(size_hint=(1, 0.9))
            scroll.add_widget(table)
            layout.add_widget(scroll)
        
        # Кнопка закрытия
        btn_close = Button(text="Закрыть", size_hint=(1, 0.1))
        btn_close.bind(on_press=popup.dismiss)
        layout.add_widget(btn_close)
        
        popup.content = layout
        popup.open()
    
    def show_income_chart(self, instance):
        """Показать диаграмму доходов"""
        try:
            now = datetime.now()
            popup = ChartPopup(self.finance_manager, now.year, now.month, "income")
            popup.open()
        except Exception as e:
            MessagePopup(title="Ошибка", message=f"Не удалось загрузить данные: {str(e)}").open()
    
    def show_expense_chart(self, instance):
        """Показать диаграмму расходов"""
        try:
            now = datetime.now()
            popup = ChartPopup(self.finance_manager, now.year, now.month, "expense")
            popup.open()
        except Exception as e:
            MessagePopup(title="Ошибка", message=f"Не удалось загрузить данные: {str(e)}").open()
    
    def show_balance_chart(self, instance):
        """Показать сравнение доходов и расходов"""
        try:
            now = datetime.now()
            chart_data = self.finance_manager.get_category_data_for_charts(now.year, now.month)
            
            layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
            
            # Заголовок
            month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                          'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
            month_name = month_names[now.month - 1]
            
            title_label = Label(
                text=f"💰 Сравнение доходов и расходов ({month_name} {now.year})",
                size_hint=(1, 0.1),
                font_size='20sp',
                bold=True
            )
            layout.add_widget(title_label)
            
            # Статистика
            stats_text = (
                f"📊 Общая статистика:\n\n"
                f"💵 Общий доход: {chart_data['total_income']:.2f} руб.\n"
                f"💸 Общие расходы: {chart_data['total_expense']:.2f} руб.\n"
                f"💰 Баланс: {chart_data['balance']:.2f} руб.\n\n"
            )
            
            if chart_data['balance'] > 0:
                stats_text += f"✅ Положительный баланс (сбережения: {chart_data['balance']:.2f} руб.)"
            elif chart_data['balance'] < 0:
                stats_text += f"❌ Отрицательный баланс (дефицит: {abs(chart_data['balance']):.2f} руб.)"
            else:
                stats_text += "⚖️ Баланс нулевой (доходы = расходам)"
            
            stats_label = Label(
                text=stats_text,
                size_hint=(1, 0.3),
                font_size='16sp'
            )
            layout.add_widget(stats_label)
            
            # Процентное соотношение
            if chart_data['total_income'] > 0:
                income_percentage = (chart_data['total_expense'] / chart_data['total_income']) * 100
                ratio_text = f"📈 Расходы составляют {income_percentage:.1f}% от доходов"
                
                if income_percentage < 70:
                    ratio_text += "\n✅ Отличное соотношение (ниже 70%)"
                elif income_percentage < 90:
                    ratio_text += "\n⚠️ Внимание (близко к 100%)"
                else:
                    ratio_text += "\n❌ Критическое соотношение (выше 90%)"
                
                ratio_label = Label(
                    text=ratio_text,
                    size_hint=(1, 0.2),
                    font_size='16sp'
                )
                layout.add_widget(ratio_label)
            
            # Кнопка закрытия
            btn_close = Button(text="Закрыть", size_hint=(1, 0.1))
            
            popup = Popup(
                title="Сравнение доходов и расходов",
                content=layout,
                size_hint=(0.8, 0.8)
            )
            
            btn_close.bind(on_press=popup.dismiss)
            layout.add_widget(btn_close)
            
            popup.open()
            
        except Exception as e:
            MessagePopup(title="Ошибка", message=f"Не удалось загрузить данные: {str(e)}").open()
    
    def show_all_charts(self, instance):
        """Показать все диаграммы"""
        try:
            now = datetime.now()
            popup = ChartPopup(self.finance_manager, now.year, now.month, "all")
            popup.open()
        except Exception as e:
            MessagePopup(title="Ошибка", message=f"Не удалось загрузить данные: {str(e)}").open()


class FinanceApp(App):
    """Основное приложение"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_listeners = []
        self.tabs = {}  # Инициализируем словарь вкладок
    
    def build(self):
        self.title = "💰 Персональный учет финансов"
        self.finance_manager = FinanceManager()
        
        # Устанавливаем цвет фона окна
        Window.clearcolor = (0.2, 0.6, 0.8, 1)
        
        # Создаем главный layout
        main_layout = BoxLayout(orientation='vertical')
        
        # Заголовок с градиентом
        header = BoxLayout(
            orientation='vertical',
            size_hint=(1, 0.15),
            padding=[20, 10]
        )
        header.background_color = (0.9, 0.95, 1, 1)
        
        title_label = Label(
            text="💰 ПЕРСОНАЛЬНЫЙ УЧЕТ ФИНАНСОВ",
            size_hint=(1, 0.7),
            font_size='28sp',
            bold=True,
            color=(1, 1, 1, 1)
        )
        
        header.add_widget(title_label)
        main_layout.add_widget(header)
        
        # Создаем TabbedPanel
        tab_panel = TabbedPanel(
            size_hint=(1, 0.85),
            do_default_tab=False,
            background_color=(0.95, 0.95, 0.95, 1),
            tab_width=150
        )
        
        # Вкладка Календарь (по умолчанию)
        calendar_tab = CalendarTab(self.finance_manager, app_instance=self)
        tab0 = TabbedPanelItem(
            text='📅 Календарь',
            background_normal='',
            background_color=(0.95, 0.95, 0.95, 1),
            color=(0.2, 0.2, 0.2, 1)
        )
        tab0.add_widget(calendar_tab)
        tab_panel.add_widget(tab0)
        tab_panel.default_tab = tab0
        
        # Вкладка операций
        transactions_tab = TransactionsTab(self.finance_manager, app_instance=self)
        tab1 = TabbedPanelItem(
            text='💳 Операции',
            background_normal='',
            background_color=(0.95, 0.95, 0.95, 1),
            color=(0.2, 0.2, 0.2, 1)
        )
        tab1.add_widget(transactions_tab)
        tab_panel.add_widget(tab1)
        
        # Вкладка категорий
        categories_tab = CategoriesTab(self.finance_manager, app_instance=self)
        tab2 = TabbedPanelItem(
            text='📁 Категории',
            background_normal='',
            background_color=(0.95, 0.95, 0.95, 1),
            color=(0.2, 0.2, 0.2, 1)
        )
        tab2.add_widget(categories_tab)
        tab_panel.add_widget(tab2)
        
        # Вкладка отчетов
        reports_tab = ReportsTab(self.finance_manager, app_instance=self)
        tab3 = TabbedPanelItem(
            text='📈 Отчеты',
            background_normal='',
            background_color=(0.95, 0.95, 0.95, 1),
            color=(0.2, 0.2, 0.2, 1)
        )
        tab3.add_widget(reports_tab)
        tab_panel.add_widget(tab3)
        
        main_layout.add_widget(tab_panel)
        
        # Сохраняем ссылки на вкладки
        self.tabs['calendar'] = calendar_tab
        self.tabs['transactions'] = transactions_tab
        self.tabs['categories'] = categories_tab
        self.tabs['reports'] = reports_tab
        
        return main_layout
    
    def refresh_all_tabs(self):
        """Принудительное обновление всех вкладок"""
        print("DEBUG: Обновление всех вкладок...")
        
        # Обновляем календарь
        calendar_tab = self.tabs.get('calendar')
        if calendar_tab:
            try:
                calendar_tab.update_calendar()
                if hasattr(calendar_tab, 'selected_date') and calendar_tab.selected_date:
                    calendar_tab.show_day_transactions(calendar_tab.selected_date)
                print("DEBUG: Календарь обновлен")
            except Exception as e:
                print(f"Ошибка при обновлении календаря: {e}")
        
        # Обновляем список операций
        transactions_tab = self.tabs.get('transactions')
        if transactions_tab:
            try:
                transactions_tab.refresh_transactions()
                print("DEBUG: Список операций обновлен")
            except Exception as e:
                print(f"Ошибка при обновлении операций: {e}")
        
        # Обновляем список категорий
        categories_tab = self.tabs.get('categories')
        if categories_tab:
            try:
                categories_tab.refresh_categories()
                print("DEBUG: Список категорий обновлен")
            except Exception as e:
                print(f"Ошибка при обновлении категорий: {e}")
        
        # Обновляем отчеты
        reports_tab = self.tabs.get('reports')
        if reports_tab:
            try:
                # Обновляем диаграммы
                reports_tab.refresh_charts()
                print("DEBUG: Отчеты обновлены")
            except Exception as e:
                print(f"Ошибка при обновлении отчетов: {e}")
        
        # Уведомляем всех слушателей
        for listener in self.data_listeners:
            try:
                listener()
            except Exception as e:
                print(f"Ошибка в слушателе: {e}")
    
    def add_data_listener(self, callback):
        """Добавить слушатель изменений данных"""
        self.data_listeners.append(callback)
    
    def remove_data_listener(self, callback):
        """Удалить слушатель изменений данных"""
        if callback in self.data_listeners:
            self.data_listeners.remove(callback)


if __name__ == "__main__":
    FinanceApp().run()   