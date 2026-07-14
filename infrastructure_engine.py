def endpoint_count(injection_rooms, uptake_rooms, existing_mrt_rooms, new_mrt_rooms, other_endpoints, include_uptake_endpoints, include_return_endpoint):
    return 1 + injection_rooms + (uptake_rooms if include_uptake_endpoints else 0) + existing_mrt_rooms + new_mrt_rooms + other_endpoints + (1 if include_return_endpoint else 0)
