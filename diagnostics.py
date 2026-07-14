def near_feasible_message(r,inp):
    if r is None:return 'No candidate generated.'
    if r.feasible:return 'A feasible plan was found.'
    if r.reason=='CapEx exceeds budget.':return f'Closest plan exceeds budget by ${max(0,r.capex-inp.maximum_capex_budget):,.0f}.'
    return f'Closest plan supports {r.installed_capacity_day:,.1f} patients/day. Binding constraint: {r.binding_constraint}.'
