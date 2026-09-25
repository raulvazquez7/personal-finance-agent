# Money rules

How tally ai adds up your money. These rules are the contract behind every number in the
dashboards and every answer of the chat agent. They live in one SQL view,
`v_transactions_enriched`; everything else only sums it.

## The numbers

| Number | What it is |
|---|---|
| **Income** | The sum of rows whose category is an income category |
| **Expenses** | The sum of rows whose category is an expense category. A refund subtracts |
| **Savings** | Income − expenses. Money you move to your own savings or investment accounts counts as saved |
| **Savings rate** | Savings ÷ income. It can be negative (you spent more than you earned). It is empty when there is no income |
| **Out of every total** | Transfers: between your own accounts, loan money received, and a card settlement once card statements are imported |

**The category decides the type, not the sign.** A row that has no category yet counts by
its sign (money in = income, money out = expense) until you categorize it; it shows as
"Uncategorized".

## Refunds take the category of the purchase

You buy clothes for €200 and return €80. Fashion shows **€120**, and your income does not
change. A refund of a card purchase gets expense categories to choose from, and a shop's
default category applies to its refunds too. The category `refunds` is only for money back
with no purchase behind it, such as cashback or a bank bonus, and it counts as income.

If the refund lands in a later month than the purchase, that later month shows the category
as negative. That is honest: the money came back that month.

## A loan is not income

Money a bank lends you is a **liability**: you pay it back. It goes to `loan_received`, a
transfer, and never counts as income. The monthly instalments are an expense
(`loan_payment`). The bank line does not split principal from interest, so neither do we.

Example: you borrow €1,500 in January and buy a laptop with it, then repay €130 a month.
January shows negative savings (you spent €1,500 more than you earned, with borrowed money),
and each later month shows the €130 instalment as spending.

Each loan is a merchant named after its contract (`Loan ····1234`). You can rename it, and
its disbursement and instalments stay together.

## Credit cards without card statements

Only your bank accounts are imported, not the card's own statements. The card's monthly
settlement is therefore the only trace of what you bought with the card. It counts as an
expense in its own group, **Credit card**, whose detail is unknown, just like a cash
withdrawal. When card statements are imported (a later version), the settlement becomes a
transfer and the card's purchases carry the categories.

## Transfers and Bizum

- **Transfers between your own accounts are neutral.** Both sides are transfers, whether or
  not the other account is imported.
- **A Bizum you receive is income; a Bizum you send is an expense.** When a friend pays you
  back their share of a dinner, you can give that Bizum the dinner's category
  (restaurants): it then subtracts, exactly like a refund.

## Comparisons

Every change is shown against the previous period of the same length: August against July,
a quarter against the quarter before. Year to date is compared with the same dates a year
earlier. When the previous period has no imported data, no change is shown. A month without
imported data is drawn as "no data", never as zero.
