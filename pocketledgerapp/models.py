from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CurrencyPreference(models.Model):
    class Currency(models.TextChoices):
        USD = "USD", "US Dollar"
        INR = "INR", "Indian Rupee"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="currency_preference"
    )
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.USD
    )

    @property
    def symbol(self):
        return "$" if self.currency == self.Currency.USD else "₹"

    def __str__(self):
        return f"{self.user} — {self.get_currency_display()}"


class Category(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=40)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "kind"], name="unique_user_category_kind"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class Transaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="transactions"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    date = models.DateField()
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"], name="txn_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.title} - {self.amount}"


class Budget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
        null=True,
        blank=True,
        limit_choices_to={"kind": Category.Kind.EXPENSE},
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name="budget_month_valid",
            ),
            models.UniqueConstraint(
                fields=["user", "category", "year", "month"],
                name="unique_user_category_monthly_budget",
            ),
        ]

    def __str__(self):
        category = self.category.name if self.category else "Overall"
        return f"{category} budget — {self.month}/{self.year}"
