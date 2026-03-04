def perms_test(user,perms_required:list):
    permissions=user.get_group_permissions()
    permissions_granted=0
    permissions_required=len(perms_required)
    passes_test=False
    for perm in perms_required:
        if perm in permissions:
            permissions_granted+=1
    if permissions_granted==permissions_required:
        passes_test=True
    
    return passes_test