import sqlite3
import csv
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import calendar
from contextlib import contextmanager

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

# Классы базы данных остаются без изменений
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
        if type_ not in ['доход', 'расход']:
            return False
        
        try:
            self.db.execute_query(
                "INSERT INTO categories (name, type) VALUES (?, ?)",
                (name, type_)
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

        if new_type not in ['доход', 'расход']:
            return False
        
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
                (new_name, new_type, category_id)
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

        print(f"DEBUG: Найдено {transactions_count} операций в категории '{name}'")


        if transactions_count > 0 and not force:
            print(f"⚠️ Категория '{name}' имеет {transactions_count} операций")
            print("❌ Удаление невозможно без подтверждения")
            return False

        try:
            if transactions_count > 0:
                print(f"⚠️ Удаление {transactions_count} операций категории '{name}'...")
                self.db.execute_query(
                    "DELETE FROM transactions WHERE category_id = ?",
                    (category_id,)
                )
                print(f"DEBUG: Операции удалены")

            self.db.execute_query(
                "DELETE FROM categories WHERE id = ?",
                (category_id,)
            )

            print(f"✅ Категория '{name}' удалена")
            if transactions_count > 0:
                print(f"   Удалено {transactions_count} операций")
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
    
    def get_all_categories(self) -> List[Tuple]:
        """Получение всех категорий"""
        return self.db.fetch_all(
            "SELECT name, type FROM categories ORDER BY type, name"
        )
    
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


class TransactionRow(BoxLayout):
    """Строка для отображения транзакции"""
    date = StringProperty("")
    category = StringProperty("")
    amount = NumericProperty(0)
    type = StringProperty("")
    description = StringProperty("")


class TransactionsView(RecycleView):
    """Вид для отображения списка транзакций"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.layout = RecycleGridLayout(
            cols=5,
            default_size=(None, dp(40)),
            size_hint_y=None,
            height=self.minimum_height
        )
        self.layout.bind(minimum_height=self.layout.setter('height'))
        
        self.viewclass = 'TransactionRow'
        self.add_widget(self.layout)


class AddTransactionPopup(Popup):
    """Окно добавления транзакции"""
    def __init__(self, finance_manager, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.callback = callback
        self.title = "Добавить операцию"
        self.size_hint = (0.9, 0.8)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        layout.add_widget(Label(text="Тип операции:", size_hint=(1, 0.1)))
        self.type_spinner = Spinner(
            text='expense',
            values=('expense', 'income'),
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
    
    def update_categories(self):
        """Обновление списка категорий"""
        categories = self.finance_manager.get_all_categories()
        current_type = self.type_spinner.text
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
            type_ = self.type_spinner.text
            
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
                if self.callback:
                    self.callback()
                self.dismiss()
            else:
                MessagePopup(title="Ошибка", message="Не удалось добавить операцию!").open()
        except ValueError:
            MessagePopup(title="Ошибка", message="Некорректная сумма!").open()


class AddCategoryPopup(Popup):
    """Окно добавления категории"""
    def __init__(self, finance_manager, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
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

        if self.callback:
            self.callback()
            self.dismiss()

        else:
            MessagePopup(title="Ошибка", message=f"Категория '{name}' уже существует!").open()
            pass

class EditCategoryPopup(Popup):
    """Окно редактирования категории"""
    def __init__(self, finance_manager, category_name, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.old_name = category_name
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
            text='',
            values=('expense', 'income'),
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
            if self.callback:
                self.callback()
            self.dismiss()
        else:
            MessagePopup(title="Ошибка", message="Не удалось обновить категорию!").open()


class DeleteCategoryPopup(Popup):
    """Окно удаления категории"""
    def __init__(self, finance_manager, category_name, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.category_name = category_name
        self.callback = callback
        self.title = f"Удалить категорию: {category_name}"
        self.size_hint = (0.8, 0.5)
        
        self.stats = finance_manager.get_category_stats(category_name)

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Статистика категории
        if self.stats:
            message = f"Категория: {category_name}\n"
            message += f"Тип: {self.stats['type']}\n"
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
                if self.callback:
                    self.callback()
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
        
        # Кнопки
        btn_layout = BoxLayout(size_hint=(1, 0.3), spacing=10)
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
            
            result = self.finance_manager.export_to_csv(year, month, filename)
            
            MessagePopup(
                title="Успех", 
                message=f"Данные экспортированы в файл:\n{result}"
            ).open()
            
            self.dismiss()
            
        except ValueError:
            MessagePopup(title="Ошибка", message="Введите корректные значения!").open()


class CategoriesTab(BoxLayout):
    """Вкладка управления категориями"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Заголовок
        self.add_widget(Label(
            text="Управление категориями",
            size_hint=(1, 0.1),
            font_size='20sp'
        ))
        
        # Список категорий
        self.categories_label = Label(
            text="",
            size_hint=(2, 0.8),
            halign='left',
            valign='top'
        )
        self.categories_label.bind(size=self.categories_label.setter('text_size'))
        
        scroll = ScrollView(size_hint=(2, 0.8))
        scroll.add_widget(self.categories_label)
        self.add_widget(scroll)
        
        # Кнопки управления
        btn_layout = GridLayout(cols=4, size_hint=(0.5, 0.2), spacing=15)
        
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
        income_cats = [c[0] for c in categories if c[1] == 'income']
        if income_cats:
            for cat in income_cats:
                text += f"  • {cat}\n"
        else:
            text += "  Нет категорий\n"
        
        text += "\n📤 Расходы:\n"
        expense_cats = [c[0] for c in categories if c[1] == 'expense']
        if expense_cats:
            for cat in expense_cats:
                text += f"  • {cat}\n"
        else:
            text += "  Нет категорий\n"
        
        self.categories_label.text = text
    
    def show_add_category(self, instance):
        """Показать окно добавления категории"""
        popup = AddCategoryPopup(self.finance_manager, self.refresh_categories)
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
        popup = EditCategoryPopup(self.finance_manager, category_name, self.refresh_categories)
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
        popup = DeleteCategoryPopup(self.finance_manager, category_name, self.refresh_categories)
        popup.open()


class TransactionsTab(BoxLayout):
    """Вкладка операций"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
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
            
            # Тип
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
        popup = AddTransactionPopup(self.finance_manager, self.refresh_transactions)
        popup.open()


class ReportsTab(BoxLayout):
    """Вкладка отчетов"""
    def __init__(self, finance_manager, **kwargs):
        super().__init__(**kwargs)
        self.finance_manager = finance_manager
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Заголовок
        self.add_widget(Label(
            text="Отчеты и анализ",
            size_hint=(1, 0.1),
            font_size='20sp'
        ))
        
        # Кнопки отчетов
        btn_layout = GridLayout(cols=2, size_hint=(1, 0.4), spacing=10, padding=20)
        
        btn_summary = Button(text='Сводка за месяц')
        btn_export = Button(text='Экспорт в CSV')
        btn_recent = Button(text='Последние операции')
        
        btn_summary.bind(on_press=self.show_summary)
        btn_export.bind(on_press=self.show_export)
        btn_recent.bind(on_press=self.show_recent)
        
        btn_layout.add_widget(btn_summary)
        btn_layout.add_widget(btn_export)
        btn_layout.add_widget(btn_recent)
        btn_layout.add_widget(Label())  # Пустая ячейка
        
        self.add_widget(btn_layout)
        
        # Область для отображения последних операций
        self.recent_label = Label(
            text="Нажмите 'Последние операции' для просмотра",
            size_hint=(1, 0.5),
            halign='left',
            valign='top'
        )
        self.recent_label.bind(size=self.recent_label.setter('text_size'))
        
        scroll = ScrollView(size_hint=(1, 0.5))
        scroll.add_widget(self.recent_label)
        self.add_widget(scroll)
    
    def show_summary(self, instance):
        """Показать сводку за месяц"""
        popup = MonthSummaryPopup(self.finance_manager)
        popup.open()
    
    def show_export(self, instance):
        """Показать окно экспорта"""
        popup = ExportCSVPopup(self.finance_manager)
        popup.open()
    
    def show_recent(self, instance):
        """Показать последние операции"""
        transactions = self.finance_manager.get_recent_transactions(20)
        
        if not transactions:
            self.recent_label.text = "📭 Нет операций"
            return
        
        text = "📋 Последние 20 операций:\n\n"
        text += f"{'Дата':<12} {'Категория':<15} {'Сумма':<12} {'Тип':<8}\n"
        text += "-" * 50 + "\n"
        
        for date, category, amount, type_, description in transactions:
            type_symbol = "➕" if type_ == 'income' else "➖"
            type_text = "Доход" if type_ == 'income' else "Расход"
            text += f"{date:<12} {category:<15} {amount:<12.2f} {type_symbol} {type_text:<7}\n"
        
        self.recent_label.text = text


class FinanceApp(App):
    """Основное приложение"""
    def build(self):
        self.title = "Персональный учет финансов"
        self.finance_manager = FinanceManager()
        
        # Создаем главный layout
        main_layout = BoxLayout(orientation='vertical')
        
        # Заголовок
        header = Label(
            text="ПЕРСОНАЛЬНЫЙ УЧЕТ ФИНАНСОВ",
            size_hint=(1, 0.2),
            font_size='25sp',
            bold=True,
            color=(0.2, 0.6, 0.8, 1)
        )
        main_layout.add_widget(header)
        
        # Создаем TabbedPanel
        tab_panel = TabbedPanel(size_hint=(1, 0.9))
        tab_panel.background_color = (0.95, 0.95, 0.95, 1)
        tab_panel.tab_width = 150
        
        # Вкладка операций
        transactions_tab = TransactionsTab(self.finance_manager)
        tab1 = TabbedPanelItem(text='Операции')
        tab1.add_widget(transactions_tab)
        tab_panel.add_widget(tab1)
        
        # Вкладка категорий
        categories_tab = CategoriesTab(self.finance_manager)
        tab2 = TabbedPanelItem(text='Категории')
        tab2.add_widget(categories_tab)
        tab_panel.add_widget(tab2)
        
        # Вкладка отчетов
        reports_tab = ReportsTab(self.finance_manager)
        tab3 = TabbedPanelItem(text='Отчеты')
        tab3.add_widget(reports_tab)
        tab_panel.add_widget(tab3)
        
        main_layout.add_widget(tab_panel)
        
        return main_layout


if __name__ == "__main__":
    FinanceApp().run()