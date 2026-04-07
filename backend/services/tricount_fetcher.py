from datetime import timezone

from backend.models import ParsedData, Expense, Allocation, Member, Balance


def fetch_from_tricount(registry_id: str) -> ParsedData:
    """
    Fetch live data from Tricount API using tricount-extractor.
    Runs synchronously — wrap in run_in_executor for async FastAPI routes.
    No credentials needed: library auto-generates RSA session keys.
    """
    from tricount_extractor.client.client import TricountClient
    from tricount_extractor.models.registry import Registry

    with TricountClient() as client:
        response = client.get_registry(registry_id)
    registry = Registry.from_json(response.json())
    return _registry_to_parsed_data(registry)


def _registry_to_parsed_data(registry) -> ParsedData:
    expenses: list[Expense] = []
    allocations: list[Allocation] = []

    for entry in registry.entries:
        date = entry.date
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        expenses.append(Expense(
            entry_id=entry.id,
            date=date,
            description=entry.description,
            amount=abs(entry.amount.value),
            currency=entry.amount.currency,
            payer=entry.payer_name,
            is_reimbursement=entry.is_reimbursement,
            category="UNCATEGORIZED",
        ))
        for alloc in entry.allocations:
            allocations.append(Allocation(
                entry_id=entry.id,
                participant=alloc.member_name,
                share=abs(alloc.amount.value),
                currency=alloc.amount.currency,
            ))

    members = [
        Member(
            member_id=m.id,
            member_name=m.display_name,
            status=m.status,
        )
        for m in registry.members
    ]

    # Compute balances from entries
    balance_map: dict[str, float] = {m.display_name: 0.0 for m in registry.members}
    for entry in registry.entries:
        balance_map[entry.payer_name] = balance_map.get(entry.payer_name, 0.0) + abs(entry.amount.value)
        for alloc in entry.allocations:
            balance_map[alloc.member_name] = balance_map.get(alloc.member_name, 0.0) - abs(alloc.amount.value)

    balances = [
        Balance(member=name, balance=round(bal, 2))
        for name, bal in sorted(balance_map.items(), key=lambda x: -x[1])
    ]

    return ParsedData(
        expenses=expenses,
        allocations=allocations,
        members=members,
        balances=balances,
    )
