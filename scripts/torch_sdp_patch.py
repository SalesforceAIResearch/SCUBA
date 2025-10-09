# --- MONKEY PATCH: promote 3D -> 4D for fused SDPA/Flash ---
import torch
import torch.nn.functional as F

if not hasattr(torch, "_sdpa_3d_to_4d_patched"):
    _orig_sdp = F.scaled_dot_product_attention

    def _sdp_4d(q, k, v, attn_mask=None, dropout_p=0.0, **kw):
        # If Q/K/V are 3D [BH, L, Dh], promote to 4D [1, BH, L, Dh]
        # so PyTorch dispatches to fused kernels instead of math_sdp.
        if q.dim() == 3:
            q = q.unsqueeze(0)
            k = k.unsqueeze(0)
            v = v.unsqueeze(0)
            if attn_mask is not None and attn_mask.dim() == 3:
                attn_mask = attn_mask.unsqueeze(0)
            out = _orig_sdp(q, k, v, attn_mask=attn_mask, dropout_p=dropout_p, **kw)
            return out.squeeze(0)
        return _orig_sdp(q, k, v, attn_mask=attn_mask, dropout_p=dropout_p, **kw)

    F.scaled_dot_product_attention = _sdp_4d  # <- patch
    torch._sdpa_3d_to_4d_patched = True
# --- END MONKEY PATCH ---

# Fail fast if patch isn't respected by dispatch
torch.backends.cuda.enable_mem_efficient_sdp(True)
torch.backends.cuda.enable_math_sdp(False)


