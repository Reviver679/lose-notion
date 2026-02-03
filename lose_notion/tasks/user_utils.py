# User Utilities for Task Bot
# Handles user lookup and fuzzy search

import frappe


def get_user_by_phone(phone_number):
    """Get user by mobile number
    
    Args:
        phone_number: Phone number (with or without country code)
        
    Returns:
        Dict with name, full_name, email or None if not found
    """
    phone = str(phone_number).replace(" ", "").replace("-", "").replace("+", "")
    
    user = frappe.db.get_value(
        "User",
        {"mobile_no": ("like", f"%{phone[-10:]}%"), "enabled": 1},
        ["name", "full_name", "email"],
        as_dict=True
    )
    return user


def fuzzy_search_user(search_term, limit=3):
    """Search for users matching the search term with improved fuzzy matching
    
    Improvements over basic character overlap:
    - Word boundary matching (e.g., "kesh" matches "Keshav")
    - First/last name separate matching
    - Email prefix matching (before @)
    - Higher scores for prefix matches
    
    Args:
        search_term: Text to search for (name or email)
        limit: Maximum number of results
        
    Returns:
        List of user dicts with name, full_name, email
    """
    if not search_term:
        return []
    
    search_term = search_term.strip().lower()
    
    # Try exact email match first
    exact_match = frappe.db.get_value(
        "User",
        {"enabled": 1, "email": search_term},
        ["name", "full_name", "email"],
        as_dict=True
    )
    if exact_match:
        return [exact_match]
    
    # Try exact full name match (case insensitive)
    exact_name = frappe.db.get_value(
        "User",
        {"enabled": 1, "full_name": ("like", search_term)},
        ["name", "full_name", "email"],
        as_dict=True
    )
    if exact_name:
        return [exact_name]
    
    # Get all system users for fuzzy matching
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "email"],
        limit=100
    )
    
    scored_users = []
    for user in users:
        score = _calculate_match_score(search_term, user)
        if score > 0:
            scored_users.append((score, user))
    
    # Sort by score descending
    scored_users.sort(key=lambda x: x[0], reverse=True)
    return [u[1] for u in scored_users[:limit]]


def _calculate_match_score(search_term, user):
    """Calculate match score for a user against search term
    
    Scoring:
    - 100: Exact match on full name or email
    - 50: Search term is prefix of first or last name
    - 40: Search term in full name or email prefix
    - 20: Partial word match
    - 0: No match
    """
    full_name = (user.full_name or "").lower()
    email = (user.email or "").lower()
    email_prefix = email.split('@')[0] if '@' in email else email
    
    score = 0
    
    # Exact match
    if search_term == full_name or search_term == email:
        return 100
    
    # Split name into parts (first name, last name, etc.)
    name_parts = full_name.split()
    
    # Check if search_term is a prefix of any name part (high score)
    for part in name_parts:
        if part.startswith(search_term):
            score += 50
            break
    
    # Check if search_term is in full name
    if search_term in full_name:
        score += 40
    
    # Check if search_term is prefix of email (before @)
    if email_prefix.startswith(search_term):
        score += 45
    elif search_term in email_prefix:
        score += 30
    
    # Check partial word match in name parts
    if score == 0:
        for part in name_parts:
            if search_term in part:
                score += 20
                break
    
    # Bonus for shorter names that match (more specific)
    if score > 0 and len(full_name) < 20:
        score += 5
    
    return score
