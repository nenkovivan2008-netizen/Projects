import sqlite3
import csv
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation

DB_PATH = Path(__file__).resolve().parent / "expenses.db"


CATEGORIES = ["Food", "Transport", "Housing", "Study", "Entertainment", "Other"]


def parse_amount(text):
    """Convert a positive euro amount into a whole number of cents."""
    try:
        amount = Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError("Enter a number such as 12.50.") from None

    if not amount.is_finite() or amount <= 0 or amount > 1_000_000:
        raise ValueError("Enter an amount above 0 and at most 1,000,000 euros.")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ValueError("Use no more than two decimal places.")
    return int(cents)


def format_money(cents):
    """Display integer cents as euros, without floating-point arithmetic."""
    return f"€{cents // 100}.{cents % 100:02d}"

def initialise_database():
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                category TEXT NOT NULL,
                description TEXT NOT NULL
            )
        """)


def load_transactions():
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT date, amount_cents, category, description
            FROM transactions
            ORDER BY id
        """).fetchall()

    return [dict(row) for row in rows]


def save_transaction(transaction):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            INSERT INTO transactions
                (date, amount_cents, category, description)
            VALUES (?, ?, ?, ?)
        """, (
            transaction["date"],
            transaction["amount_cents"],
            transaction["category"],
            transaction["description"],
        ))

def add_transaction(transactions):
    """Ask for one expense and append its dictionary to our list."""
    while True:
        text = input("Date (YYYY-MM-DD, Enter for today): ").strip()
        if not text:
            text = date.today().isoformat()
        try:
            transaction_date = date.fromisoformat(text)
            if transaction_date.isoformat() != text:
                raise ValueError
            break
        except ValueError:
            print("Enter a real date using YYYY-MM-DD, such as 2026-10-08.")

    while True:
        try:
            amount_cents = parse_amount(input("Amount in euros: "))
            break
        except ValueError as error:
            print(error)

    for number, category in enumerate(CATEGORIES, start=1):
        print(f"{number}. {category}")

    while True:
        choice = input("Category number: ").strip()
        if choice in [str(number) for number in range(1, len(CATEGORIES) + 1)]:
            category = CATEGORIES[int(choice) - 1]
            break
        print(f"Choose a number from 1 to {len(CATEGORIES)}.")

    description = input("Description (optional): ").strip()
    transaction = {
        "date": transaction_date.isoformat(),
        "amount_cents": amount_cents,
        "category": category,
        "description": description,
    }
    save_transaction(transaction)
    transactions.append(transaction)
    print("Expense saved.")


def view_transactions(transactions):
    if not transactions:
        print("No expenses yet.")
        return

    for transaction in transactions:
        print(
            f"{transaction['date']} | "
            f"{format_money(transaction['amount_cents'])} | "
            f"{transaction['category']} | {transaction['description']}"
        )


def calculate_monthly_totals(transactions, month):
    """Return the month's total and a dictionary of category totals."""
    total = 0
    category_totals = {category: 0 for category in CATEGORIES}

    for transaction in transactions:
        if transaction["date"][:7] == month:
            amount = transaction["amount_cents"]
            total += amount
            category_totals[transaction["category"]] += amount

    return total, category_totals


def view_monthly_totals(transactions):
    while True:
        month = input("Month (YYYY-MM, Enter for this month): ").strip()
        if not month:
            month = date.today().isoformat()[:7]
        try:
            first_day = date.fromisoformat(month + "-01")
            if first_day.isoformat()[:7] != month:
                raise ValueError
            break
        except ValueError:
            print("Enter a valid month such as 2026-10.")

    total, category_totals = calculate_monthly_totals(transactions, month)
    print(f"\nExpenses for {month}: {format_money(total)}")
    for category, amount in category_totals.items():
        print(f"  {category}: {format_money(amount)}")

def import_csv(transactions):
    file_path = input("CSV file path: ").strip().strip("\"'")
    file_path = Path(file_path).expanduser()

    imported = 0
    duplicates = 0
    invalid = 0

    # Allow categories such as "food" or "FOOD".
    category_names = {
        category.lower(): category for category in CATEGORIES
    }

    try:
        with file_path.open(
            mode="r", encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.DictReader(file, strict=True)

            expected_columns = [
                "date", "amount", "category", "description"
            ]

            if reader.fieldnames != expected_columns:
                print(
                    "Headers must be: "
                    "date,amount,category,description"
                )
                return

            for row in reader:
                try:
                    # Reject missing fields or extra unquoted commas.
                    if None in row or None in row.values():
                        raise ValueError("Wrong number of columns.")

                    date_text = row["date"].strip()
                    parsed_date = date.fromisoformat(date_text)

                    if parsed_date.isoformat() != date_text:
                        raise ValueError("Use YYYY-MM-DD for dates.")

                    amount_cents = parse_amount(row["amount"])

                    category = category_names.get(
                        row["category"].strip().lower()
                    )

                    if category is None:
                        raise ValueError("Unknown category.")

                    transaction = {
                        "date": date_text,
                        "amount_cents": amount_cents,
                        "category": category,
                        "description": row["description"].strip(),
                    }

                except ValueError as error:
                    print(f"Line {reader.line_num}: skipped — {error}")
                    invalid += 1
                    continue

                if transaction in transactions:
                    duplicates += 1
                    continue

                save_transaction(transaction)
                transactions.append(transaction)
                imported += 1

    except (OSError, UnicodeError, csv.Error) as error:
        print(f"Could not finish reading the CSV: {error}")

    print(
        f"Imported: {imported} | "
        f"Duplicates skipped: {duplicates} | "
        f"Invalid rows skipped: {invalid}"
    )

def main():
    initialise_database()
    transactions = load_transactions()
    print("Personal Expense Tracker — Step 2")
    print(f"Loaded {len(transactions)} saved expenses.")

    while True:
        print(
            "\n1. Add expense"
            "\n2. View expenses"
            "\n3. Monthly totals"
            "\n4. Quit"
            "\n5. Import CSV"
        )
        choice = input("Choose an option: ").strip()
        if choice == "1":
            add_transaction(transactions)
        elif choice == "2":
            view_transactions(transactions)
        elif choice == "3":
            view_monthly_totals(transactions)
        elif choice == "4":
            print("Goodbye! Your expenses are saved.")
            break
        elif choice == "5":
            import_csv(transactions)
        else:
            print("Choose 1, 2, 3, 4, or 5.")


if __name__ == "__main__":
    main()
