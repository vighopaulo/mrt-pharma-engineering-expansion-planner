def validate(inp):
    inp=inp.normalized();issues=[]
    if inp.target_patients<=0:issues.append("Target must be positive")
    if len({inp.priority_1,inp.priority_2,inp.priority_3})!=3:issues.append("Priorities must be different")
    if inp.project_mode.value=="Greenfield" and any([inp.current_patients,inp.current_scanners,inp.current_injection_rooms,inp.current_uptake_rooms,inp.current_batches]):
        issues.append("Greenfield normalization failed")
    return issues
