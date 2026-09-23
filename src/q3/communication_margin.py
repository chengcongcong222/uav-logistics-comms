"""Unified communication margin M_C (single definition for all Q3 modules)."""
from __future__ import annotations

from src.q3.link_budget import distance_m, fspl_db, load_comm_params, margin_db, path_loss_db
from src.q3.terrain_los import is_blocked


def margin_direct(
    params,
    eps,
    dem,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    force_los: bool = False,
) -> tuple[float, bool, float, float, float]:
    """Return (M_C, blocked, L_fspl, L_path, L_max) for transport<->G01 style endpoints.

    Callers pass matching RadioEndpoints via pair='T-G'|'T-R'|'R-G'.
    """
    raise NotImplementedError


def margin_pair(
    params,
    l_max: float,
    dem,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    force_los: bool = False,
) -> tuple[float, bool, float, float]:
    """M_C = Lmax - Lpath. Returns (M_C, blocked, L_fspl, L_path)."""
    d = distance_m(a, b)
    blocked = False if force_los else is_blocked(dem, a, b)
    l_fspl = fspl_db(params.f_mhz, d)
    l_path = path_loss_db(params, d, blocked)
    return margin_db(l_max, l_path), blocked, l_fspl, l_path


def margin_transport_g01(params, l_max_tg, dem, tpos, gpos, force_los=False):
    return margin_pair(params, l_max_tg, dem, tpos, gpos, force_los)


def margin_transport_relay(params, l_max_tr, dem, tpos, rpos, force_los=False):
    return margin_pair(params, l_max_tr, dem, tpos, rpos, force_los)


def margin_relay_g01(params, l_max_rg, dem, rpos, gpos, force_los=False):
    return margin_pair(params, l_max_rg, dem, rpos, gpos, force_los)


def margin_relay_two_hop(params, l_max_tr, l_max_rg, dem, tpos, rpos, gpos) -> tuple[float, float, float]:
    """M_UR, M_RG, M_relay=min(...)."""
    mur, _, _, _ = margin_transport_relay(params, l_max_tr, dem, tpos, rpos)
    mrg, _, _, _ = margin_relay_g01(params, l_max_rg, dem, rpos, gpos)
    return mur, mrg, min(mur, mrg)
