from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Budget, Category, Transaction


class PocketLedgerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ledger-user", password="SafePass123!xyz")
        self.other_user = User.objects.create_user(
            username="other-user", password="SafePass123!xyz"
        )
        self.expense_category = Category.objects.create(
            user=self.user, name="Food", kind=Category.Kind.EXPENSE
        )
        self.income_category = Category.objects.create(
            user=self.user, name="Salary", kind=Category.Kind.INCOME
        )
        self.other_category = Category.objects.create(
            user=self.other_user, name="Private", kind=Category.Kind.EXPENSE
        )
        self.client.force_login(self.user)

    def test_dashboard_only_shows_current_users_data(self):
        own = Transaction.objects.create(
            user=self.user,
            category=self.expense_category,
            kind=Transaction.Kind.EXPENSE,
            title="Groceries",
            amount=Decimal("45.50"),
            date=date.today(),
        )
        Transaction.objects.create(
            user=self.other_user,
            category=self.other_category,
            kind=Transaction.Kind.EXPENSE,
            title="Private purchase",
            amount=Decimal("999.00"),
            date=date.today(),
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Groceries")
        self.assertNotContains(response, "Private purchase")
        self.assertEqual(list(response.context["transactions"]), [own])
        self.assertEqual(response.context["balance"], Decimal("-45.50"))

    def test_create_transaction_validates_type_and_user_owned_category(self):
        response = self.client.post(
            reverse("transaction-create"),
            {
                "kind": "expense",
                "title": "Book",
                "amount": "18.25",
                "category": self.expense_category.pk,
                "date": "2026-10-01",
                "note": "",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(
            Transaction.objects.filter(
                user=self.user, title="Book", amount=Decimal("18.25")
            ).exists()
        )

        self.client.post(
            reverse("transaction-create"),
            {
                "kind": "income",
                "title": "Invalid category",
                "amount": "12",
                "category": self.expense_category.pk,
                "date": "2026-10-01",
            },
        )
        self.assertFalse(Transaction.objects.filter(title="Invalid category").exists())
        self.client.post(
            reverse("transaction-create"),
            {
                "kind": "expense",
                "title": "Foreign category",
                "amount": "12",
                "category": self.other_category.pk,
                "date": "2026-10-01",
            },
        )
        self.assertFalse(Transaction.objects.filter(title="Foreign category").exists())

    def test_update_and_delete_cannot_access_another_users_transaction(self):
        private_transaction = Transaction.objects.create(
            user=self.other_user,
            category=self.other_category,
            kind=Transaction.Kind.EXPENSE,
            title="Private",
            amount=Decimal("12.00"),
            date=date.today(),
        )
        edit_response = self.client.post(
            reverse("transaction-update", args=[private_transaction.pk]),
            {"kind": "expense", "title": "Changed", "amount": "2", "category": self.expense_category.pk, "date": "2026-10-01"},
        )
        delete_response = self.client.post(
            reverse("transaction-delete", args=[private_transaction.pk])
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        private_transaction.refresh_from_db()
        self.assertEqual(private_transaction.title, "Private")

    def test_budget_is_saved_and_updated_for_its_month(self):
        url = reverse("budget-save")
        data = {"category": "", "amount": "500.00", "year": "2026", "month": "10"}
        self.assertRedirects(self.client.post(url, data), reverse("dashboard"))
        self.assertEqual(Budget.objects.filter(user=self.user).count(), 1)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Monthly budget")
        self.assertEqual(len(dashboard.context["budget_form"].fields["month"].choices), 12)

        data["amount"] = "650.00"
        self.client.post(url, data)
        budget = Budget.objects.get(user=self.user)
        self.assertEqual(budget.amount, Decimal("650.00"))
        self.assertEqual(Budget.objects.filter(user=self.user).count(), 1)

    def test_filters_search_and_date_range(self):
        Transaction.objects.create(
            user=self.user,
            category=self.expense_category,
            kind=Transaction.Kind.EXPENSE,
            title="Coffee",
            amount=Decimal("5.00"),
            date=date(2026, 10, 4),
        )
        Transaction.objects.create(
            user=self.user,
            category=self.income_category,
            kind=Transaction.Kind.INCOME,
            title="Paycheck",
            amount=Decimal("100.00"),
            date=date(2026, 9, 30),
        )

        response = self.client.get(
            reverse("dashboard"),
            {"q": "coffee", "kind": "expense", "start": "2026-10-01", "end": "2026-10-31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "Coffee")
        self.assertNotContains(response, "Paycheck")

    def test_registration_creates_account_and_default_categories(self):
        self.client.logout()
        response = self.client.post(
            reverse("dashboard"),
            {
                "auth_action": "register",
                "username": "new-ledger",
                "email": "new@example.com",
                "password1": "L3dger!Password912",
                "password2": "L3dger!Password912",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        new_user = User.objects.get(username="new-ledger")
        self.assertEqual(int(self.client.session["_auth_user_id"]), new_user.pk)
        self.assertTrue(Category.objects.filter(user=new_user, kind=Category.Kind.EXPENSE).exists())

    def test_mutations_require_login_and_post(self):
        self.client.logout()
        response = self.client.post(
            reverse("transaction-create"),
            {"kind": "expense", "title": "Nope", "amount": "3", "category": self.expense_category.pk, "date": "2026-10-01"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard"), response["Location"])

        self.client.force_login(self.user)
        response = self.client.get(reverse("transaction-create"))
        self.assertEqual(response.status_code, 405)

    def test_currency_choice_persists_per_user_and_updates_dashboard(self):
        transaction = Transaction.objects.create(
            user=self.user,
            category=self.expense_category,
            kind=Transaction.Kind.EXPENSE,
            title="Currency display test",
            amount=Decimal("45.50"),
            date=date.today(),
        )
        initial = self.client.get(reverse("dashboard"))
        self.assertEqual(initial.context["currency_preference"].currency, "USD")
        self.assertEqual(initial.context["currency_symbol"], "$")
        self.assertContains(initial, "$45.50")

        response = self.client.post(reverse("currency-update"), {"currency": "INR"})
        self.assertRedirects(response, reverse("dashboard"))
        inr_dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(inr_dashboard.context["currency_preference"].currency, "INR")
        self.assertEqual(inr_dashboard.context["currency_symbol"], "₹")
        self.assertEqual(inr_dashboard.context["chart_data"]["currency_symbol"], "₹")
        self.assertContains(inr_dashboard, "₹")
        self.assertContains(inr_dashboard, "₹45.50")
        self.assertContains(inr_dashboard, "Indian Rupee")
        transaction.refresh_from_db()
        self.assertEqual(transaction.amount, Decimal("45.50"))

        self.client.post(reverse("currency-update"), {"currency": "EUR"})
        unchanged = self.client.get(reverse("dashboard"))
        self.assertEqual(unchanged.context["currency_preference"].currency, "INR")

        self.client.force_login(self.other_user)
        other_dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(other_dashboard.context["currency_preference"].currency, "USD")
        self.assertEqual(other_dashboard.context["currency_symbol"], "$")
