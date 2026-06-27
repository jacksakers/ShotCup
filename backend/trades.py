from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List

from database import get_db
from models import TradeCreate, TradeRespond, TradeResponse
from helpers import (
    require_site_auth,
    require_admin_auth,
    _recalculate_all_scores,
    _row_to_trade_response
)

trades_router = APIRouter()


@trades_router.get("/api/trades", response_model=List[TradeResponse], tags=["Trades"])
def list_trades(
    user_id: Optional[int] = Query(None, description="Filter trades involving this user"),
    trade_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    _auth=Depends(require_site_auth),
):
    """List trades, optionally filtered by user or status."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades ORDER BY created_at DESC").fetchall()
        trades_list = []
        for r in rows:
            trade_dict = _row_to_trade_response(conn, r)
            
            # Filter status
            if trade_status and trade_dict["status"].lower() != trade_status.lower():
                continue
                
            # Filter user (proposer, receiver, or potential receiver)
            if user_id is not None:
                is_proposer = trade_dict["proposer_id"] == user_id
                is_receiver = trade_dict["receiver_id"] == user_id
                is_potential = False
                
                if trade_dict["status"] == "Pending":
                    req_ids = trade_dict["requested_team_ids"]
                    if req_ids:
                        placeholders = ",".join("?" for _ in req_ids)
                        teams = conn.execute(
                            f"SELECT owner_id FROM teams WHERE id IN ({placeholders})", req_ids
                        ).fetchall()
                        owners = {team["owner_id"] for team in teams if team["owner_id"] is not None}
                        if user_id in owners:
                            is_potential = True
                            
                if not (is_proposer or is_receiver or is_potential):
                    continue
                    
            trades_list.append(trade_dict)
            
    return trades_list


@trades_router.post("/api/trades", response_model=TradeResponse, status_code=201, tags=["Trades"])
def propose_trade(req: TradeCreate, _auth=Depends(require_site_auth)):
    """Propose a trade: offer one or two of your teams in exchange for some other teams."""
    if not req.offered_team_ids:
        raise HTTPException(status_code=400, detail="Must offer at least one team")
    if len(req.offered_team_ids) > 2:
        raise HTTPException(status_code=400, detail="Cannot offer more than two teams")
    if not req.requested_team_ids:
        raise HTTPException(status_code=400, detail="Must request at least one team")
        
    with get_db() as conn:
        # Validate proposer owns all offered teams
        placeholders = ",".join("?" for _ in req.offered_team_ids)
        offered_rows = conn.execute(
            f"SELECT id, owner_id FROM teams WHERE id IN ({placeholders})", req.offered_team_ids
        ).fetchall()
        
        if len(offered_rows) != len(req.offered_team_ids):
            raise HTTPException(status_code=400, detail="One or more offered teams do not exist")
            
        for row in offered_rows:
            if row["owner_id"] != req.proposer_id:
                raise HTTPException(status_code=400, detail=f"You do not own offered team ID {row['id']}")
                
        # Validate requested teams
        placeholders_req = ",".join("?" for _ in req.requested_team_ids)
        requested_rows = conn.execute(
            f"SELECT id, owner_id FROM teams WHERE id IN ({placeholders_req})", req.requested_team_ids
        ).fetchall()
        
        if len(requested_rows) != len(req.requested_team_ids):
            raise HTTPException(status_code=400, detail="One or more requested teams do not exist")
            
        for row in requested_rows:
            if not row["owner_id"]:
                raise HTTPException(status_code=400, detail=f"Requested team ID {row['id']} has no owner")
            if row["owner_id"] == req.proposer_id:
                raise HTTPException(status_code=400, detail="Cannot request your own team")
                
        # Prevent duplicate pending trades
        offered_str = ",".join(str(x) for x in sorted(req.offered_team_ids))
        requested_str = ",".join(str(x) for x in sorted(req.requested_team_ids))
        
        duplicate = conn.execute(
            """
            SELECT id FROM trades
            WHERE proposer_id = ? AND offered_team_ids = ? AND requested_team_ids = ?
              AND status = 'Pending'
            """,
            (req.proposer_id, offered_str, requested_str),
        ).fetchone()
        
        if duplicate:
            raise HTTPException(status_code=409, detail="Identical trade already pending")
            
        cursor = conn.execute(
            """
            INSERT INTO trades (proposer_id, offered_team_ids, requested_team_ids, status)
            VALUES (?, ?, ?, 'Pending')
            """,
            (req.proposer_id, offered_str, requested_str),
        )
        trade_id = cursor.lastrowid
        
        return _row_to_trade_response(conn, conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone())


@trades_router.put("/api/trades/{trade_id}/respond", response_model=TradeResponse, tags=["Trades"])
def respond_to_trade(trade_id: int, req: TradeRespond, _auth=Depends(require_site_auth)):
    """Accept or reject a pending trade."""
    with get_db() as conn:
        trade_row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not trade_row:
            raise HTTPException(status_code=404, detail="Trade not found")
            
        trade = dict(trade_row)
        if trade["status"] != "Pending":
            raise HTTPException(status_code=400, detail="Trade is no longer pending")
            
        if req.action == "reject":
            req_ids = [int(x) for x in trade["requested_team_ids"].split(",") if x.strip()]
            placeholders = ",".join("?" for _ in req_ids)
            teams = conn.execute(
                f"SELECT owner_id FROM teams WHERE id IN ({placeholders})", req_ids
            ).fetchall()
            owners = {team["owner_id"] for team in teams if team["owner_id"] is not None}
            
            if req.user_id not in owners and req.user_id != trade["receiver_id"]:
                raise HTTPException(status_code=403, detail="You are not a receiver of this trade")
                
            conn.execute("UPDATE trades SET receiver_id = ?, status = 'Rejected' WHERE id = ?", (req.user_id, trade_id))
            return _row_to_trade_response(conn, conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone())
            
        # action is "accept"
        if not req.accepted_team_id:
            raise HTTPException(status_code=400, detail="Must specify which requested team you are giving up")
            
        req_ids = [int(x) for x in trade["requested_team_ids"].split(",") if x.strip()]
        if req.accepted_team_id not in req_ids:
            raise HTTPException(status_code=400, detail="Selected team is not part of this trade request")
            
        team_row = conn.execute(
            "SELECT owner_id, name FROM teams WHERE id = ?", (req.accepted_team_id,)
        ).fetchone()
        if not team_row or team_row["owner_id"] != req.user_id:
            raise HTTPException(status_code=400, detail="You do not own the accepted team")
            
        offered_ids = [int(x) for x in trade["offered_team_ids"].split(",") if x.strip()]
        placeholders_offered = ",".join("?" for _ in offered_ids)
        offered_rows = conn.execute(
            f"SELECT id, owner_id FROM teams WHERE id IN ({placeholders_offered})", offered_ids
        ).fetchall()
        for row in offered_rows:
            if row["owner_id"] != trade["proposer_id"]:
                raise HTTPException(status_code=400, detail="Proposer no longer owns the offered teams")
                
        # Swap ownership
        for off_id in offered_ids:
            conn.execute("UPDATE teams SET owner_id = ? WHERE id = ?", (req.user_id, off_id))
            
        conn.execute("UPDATE teams SET owner_id = ? WHERE id = ?", (trade["proposer_id"], req.accepted_team_id))
        
        conn.execute(
            "UPDATE trades SET receiver_id = ?, accepted_team_id = ?, status = 'Accepted' WHERE id = ?",
            (req.user_id, req.accepted_team_id, trade_id)
        )
        
        # Cancel other pending trades involving any of the traded teams
        all_involved = offered_ids + [req.accepted_team_id]
        for t in conn.execute("SELECT id, offered_team_ids, requested_team_ids FROM trades WHERE status = 'Pending' AND id != ?", (trade_id,)).fetchall():
            t_offered = [int(x) for x in t["offered_team_ids"].split(",") if x.strip()]
            t_requested = [int(x) for x in t["requested_team_ids"].split(",") if x.strip()]
            if any(tid in all_involved for tid in t_offered + t_requested):
                conn.execute("UPDATE trades SET status = 'Rejected' WHERE id = ?", (t["id"],))
                
        _recalculate_all_scores(conn)
        return _row_to_trade_response(conn, conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone())


@trades_router.delete("/api/admin/trades/{trade_id}", tags=["Admin"])
def veto_trade(trade_id: int, _auth=Depends(require_admin_auth)):
    """Cancel or reverse a trade."""
    with get_db() as conn:
        trade_row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not trade_row:
            raise HTTPException(status_code=404, detail="Trade not found")

        trade = dict(trade_row)

        if trade["status"] == "Accepted":
            offered_ids = [int(x) for x in trade["offered_team_ids"].split(",") if x.strip()]
            for off_id in offered_ids:
                conn.execute("UPDATE teams SET owner_id = ? WHERE id = ?", (trade["proposer_id"], off_id))
            conn.execute("UPDATE teams SET owner_id = ? WHERE id = ?", (trade["receiver_id"], trade["accepted_team_id"]))
            
            conn.execute("UPDATE trades SET status = 'Vetoed' WHERE id = ?", (trade_id,))
            _recalculate_all_scores(conn)
        elif trade["status"] == "Pending":
            conn.execute("UPDATE trades SET status = 'Rejected' WHERE id = ?", (trade_id,))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot veto a trade with status '{trade['status']}'",
            )

    return {"message": "Trade vetoed"}
