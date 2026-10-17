# Files

- [Categorization cascade](categorization-cascade.md) - How a production run pairs own-account transfers, applies system rules, asks jev once, resolves merchants, applies defaults, and gates review without overwriting user labels.
- [Chat agent](chat-agent.md) - The shipped household-finance chat is one ReAct agent with a single read-only SQL tool, a YAML semantic layer checked at startup, and separate stores for agent memory and the history the user sees.
- [Money rules](money-rules.md) - Where the money contract is implemented, and what a new total must sum so dashboards and the chat agent stay on the same numbers.
