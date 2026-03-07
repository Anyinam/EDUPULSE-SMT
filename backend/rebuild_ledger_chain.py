#!/usr/bin/env python3
"""
Rebuild Ledger Chain - Fixes broken chain from seed.py transaction issue.

When seed.py creates multiple ledger entries in a single uncommitted transaction,
the hash references break because each entry queries for the last hash before 
the previous entry is committed. This script rebuilds the chain correctly.

Usage:
    python rebuild_ledger_chain.py [school_id]
    
    If school_id not provided, rebuilds for all schools.
"""

import sys
from backend.api.api import app, db
from backend.api.models import LedgerEntry, verify_ledger_chain, _ledger_hash, _ledger_payload

def rebuild_chain_for_school(school_id):
    """Rebuild the hash chain for a specific school."""
    print(f"\n{'='*60}")
    print(f"Rebuilding ledger chain for school: {school_id}")
    print(f"{'='*60}")
    
    # Get all entries in creation order
    entries = (
        db.session.query(LedgerEntry)
        .filter_by(school_id=school_id)
        .order_by(LedgerEntry.id.asc())
        .all()
    )
    
    if not entries:
        print(f"✓ No entries found for {school_id}")
        return True
    
    print(f"Found {len(entries)} entries. Rebuilding chain...")
    
    expected_previous_hash = "GENESIS"
    errors = []
    
    for idx, entry in enumerate(entries, 1):
        # Reconstruct the exact payload
        payload = {
            "school_id": entry.school_id,
            "tx_type": entry.tx_type,
            "tx_ref": entry.tx_ref,
            "amount": entry.amount,
            "currency": entry.currency,
            "actor_id": entry.actor_id,
            "student_id": entry.student_id,
            "source": entry.source,
            "metadata": entry.meta,
            "created_at": entry.created_at.isoformat(),
        }
        
        payload_str = _ledger_payload(payload)
        correct_hash = _ledger_hash(expected_previous_hash, payload_str)
        
        # Update entry with correct chain linkage
        old_prev = entry.previous_hash
        old_hash = entry.hash
        
        entry.previous_hash = expected_previous_hash
        entry.hash = correct_hash
        entry.is_verified = True
        
        if old_hash != correct_hash:
            errors.append({
                "id": entry.id,
                "tx_ref": entry.tx_ref,
                "old_hash": old_hash[:16] + "..." if old_hash else None,
                "new_hash": correct_hash[:16] + "...",
            })
        
        expected_previous_hash = correct_hash
        
        # Progress indicator
        if idx % 5 == 0:
            print(f"  ✓ Processed {idx}/{len(entries)} entries")
    
    # Commit changes
    db.session.commit()
    
    print(f"\n✓ Chain rebuilt successfully")
    if errors:
        print(f"  Fixed {len(errors)} broken hashes")
    
    # Verify the new chain
    print(f"\nVerifying chain integrity...")
    is_valid, broken, total = verify_ledger_chain(school_id)
    
    if is_valid:
        print(f"✓ CHAIN VERIFIED - All {total} entries are cryptographically valid")
        return True
    else:
        print(f"✗ Chain verification failed: {len(broken)} broken entries")
        for entry in broken[:3]:  # Show first 3 errors
            print(f"    Entry {entry['id']}: {entry['issue']}")
        return False


def main():
    with app.app_context():
        if len(sys.argv) > 1:
            school_id = sys.argv[1]
            success = rebuild_chain_for_school(school_id)
        else:
            # Rebuild for all schools that have ledger entries
            schools = db.session.query(LedgerEntry.school_id).distinct().all()
            school_ids = [s[0] for s in schools]
            
            if not school_ids:
                print("✓ No ledger entries found. Nothing to rebuild.")
                return
            
            print(f"Found {len(school_ids)} schools with ledger entries")
            success = True
            
            for school_id in school_ids:
                if not rebuild_chain_for_school(school_id):
                    success = False
        
        print(f"\n{'='*60}")
        if success:
            print("✅ Chain rebuild complete - Audit integrity restored")
        else:
            print("⚠️  Chain rebuild encountered issues - check output above")
        print(f"{'='*60}\n")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
