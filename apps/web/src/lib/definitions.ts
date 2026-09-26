/** The ⓘ texts on the KPI tiles, quoted from docs/money-rules.md ("The numbers"). Change them
 * there first: the dashboards and the slice 4 agent must never disagree. */
export const DEFINITIONS = {
  income: "The sum of income-type rows: rows with an income category, and uncategorized money in.",
  expenses:
    "Minus the sum of expense-type rows: rows with an expense category, and uncategorized money out. A refund (money in with an expense category) subtracts.",
  savings: "Income − expenses. Money you move to your own savings or investment accounts counts as saved.",
  savingsRate:
    "Savings ÷ income. It can be negative (you spent more than you earned). It is empty when there is no income.",
} as const;
