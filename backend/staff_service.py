from datetime import datetime, timedelta, timezone


def add_staff_member(
    data,
    school_id,
    user_model,
    school_model,
    password_hash_fn,
    normalize_email_address,
    find_school_user_by_email,
    normalize_staff_roles,
    normalize_homeroom_assignment,
    generate_staff_temp_password,
    replace_teacher_assignments,
    send_staff_invite_email,
    tenant_email_delivery_failure_message,
    db_session,
):
    email = normalize_email_address(data.get("email"))
    if not email:
        return None, {"message": "Email is required for staff accounts."}, 400

    username = data.get("username")
    if user_model.query.filter_by(username=username, school_id=school_id).first():
        return None, {"message": "Username already exists in this school."}, 400

    if find_school_user_by_email(school_id, email):
        return None, {"message": "Email address is already assigned to another staff member in this school."}, 400

    roles, primary_role, role_error = normalize_staff_roles(
        data.get("roles") if isinstance(data.get("roles"), list) else [],
        data.get("role"),
    )
    if role_error:
        return None, {"message": role_error}, 400

    assigned_class, assigned_class_error = normalize_homeroom_assignment(
        roles,
        data.get("assigned_class"),
    )
    if assigned_class_error:
        return None, {"message": assigned_class_error}, 400

    temp_password = generate_staff_temp_password()
    temp_expires = datetime.now(timezone.utc) + timedelta(days=30)

    new_user = user_model(
        username=username,
        email=email,
        role=primary_role,
        roles=roles,
        school_id=school_id,
        password_hash=password_hash_fn(temp_password),
        is_temp_password=True,
        temp_password_expires_at=temp_expires,
        assigned_class=assigned_class,
    )
    db_session.add(new_user)
    db_session.commit()

    if "homeroom" in roles or "teacher" in roles:
        replace_teacher_assignments(
            new_user.id,
            data.get("assigned_classes", []),
            data.get("assigned_subjects", []),
        )
        db_session.commit()

    school = school_model.query.get(school_id)
    email_sent, email_error = send_staff_invite_email(
        new_user,
        school,
        temp_password,
        expiry_days=30,
    )

    status_message = "Staff member added successfully."
    if email_sent:
        status_message += " Welcome email sent with login credentials."
    else:
        status_message += f" {tenant_email_delivery_failure_message()}"

    return {
        "message": status_message,
        "username": username,
        "email": email,
        "password_expires_in_days": 30,
        "email_sent": email_sent,
        "email_error": email_error,
    }, None, 200


def resend_staff_invite(
    user_id,
    school_id,
    actor_id,
    user_model,
    school_model,
    password_hash_fn,
    generate_staff_temp_password,
    send_staff_invite_email,
    tenant_email_delivery_failure_message,
    log_action,
    db_session,
):
    user = user_model.query.filter_by(id=user_id, school_id=school_id).first_or_404()
    if user.role == "proprietor":
        return None, {"message": "Cannot resend invite for proprietor accounts."}, 400

    if not user.email:
        return None, {"message": "This staff account has no email address on file."}, 400

    temp_password = generate_staff_temp_password()
    temp_expires = datetime.now(timezone.utc) + timedelta(days=30)

    school = school_model.query.get(school_id)
    email_sent, email_error = send_staff_invite_email(
        user,
        school,
        temp_password,
        expiry_days=30,
    )

    if email_sent:
        user.password_hash = password_hash_fn(temp_password)
        user.is_temp_password = True
        user.temp_password_expires_at = temp_expires

    log_action(
        actor_id,
        school_id,
        "STAFF_INVITE_RESENT",
        f"Resend invite attempted for user {user.username}; email_sent={email_sent}",
    )
    db_session.commit()

    if email_sent:
        status_message = "Staff invite resent successfully. A fresh temporary password was emailed to the staff member."
    else:
        status_message = "Staff invite email could not be delivered right now. The previous login credentials remain unchanged."

    return {
        "message": status_message,
        "username": user.username,
        "email": user.email,
        "password_expires_in_days": 30 if email_sent else None,
        "email_sent": email_sent,
        "email_error": email_error,
    }, None, 200


def update_staff_member(
    user_id,
    data,
    school_id,
    actor_id,
    user_model,
    teacher_assignment_model,
    normalize_email_address,
    find_school_user_by_email,
    normalize_staff_roles,
    normalize_homeroom_assignment,
    replace_teacher_assignments,
    log_action,
    db_session,
):
    user = user_model.query.filter_by(id=user_id, school_id=school_id).first_or_404()

    if "email" in data:
        email = normalize_email_address(data.get("email"))
        if not email:
            return None, {"message": "Email is required for staff accounts."}, 400
        if find_school_user_by_email(school_id, email, exclude_user_id=user.id):
            return None, {"message": "Email address is already assigned to another staff member in this school."}, 400
        user.email = email

    roles = (
        data.get("roles")
        if isinstance(data.get("roles"), list)
        else (user.roles or [user.role])
    )
    primary_role = data.get("role", user.role)
    if roles:
        primary_role = roles[0]

    roles, primary_role, role_error = normalize_staff_roles(roles, primary_role)
    if role_error:
        return None, {"message": role_error}, 400

    assigned_class, assigned_class_error = normalize_homeroom_assignment(
        roles,
        data.get("assigned_class", user.assigned_class),
    )
    if assigned_class_error:
        return None, {"message": assigned_class_error}, 400

    user.role = primary_role
    user.roles = roles
    user.assigned_class = assigned_class

    if "homeroom" in roles or "teacher" in roles:
        if "assigned_classes" in data or "assigned_subjects" in data:
            replace_teacher_assignments(
                user.id,
                data.get("assigned_classes", []),
                data.get("assigned_subjects", []),
            )
    else:
        teacher_assignment_model.query.filter_by(
            school_id=school_id,
            teacher_id=user.id,
        ).delete()

    log_action(
        actor_id,
        school_id,
        "STAFF_UPDATED",
        f"Updated user {user.username} to roles {', '.join(roles)}",
    )
    db_session.commit()
    return {"message": "Staff member updated."}, None, 200