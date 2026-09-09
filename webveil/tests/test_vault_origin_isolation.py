"""
Security Automated Test Suite for Vault Out-of-DOM Fingerprint, Origin Isolation, and Exfiltration Prevention.
Tests verify that the vault's Python-side node fingerprint registry rejects identity spoofing,
and that downstream checks (element type, opacity, bbox) independently reject their respective attacks.
"""

import pytest
from webveil.core.models.schema import DOMNode, PIIMatch, PIICategory
from webveil.core.vault.client_vault import ClientVault, VaultRestorationError


@pytest.fixture
def vault_setup():
    vault = ClientVault(current_origin="https://bank.example.com")
    match = PIIMatch(
        category=PIICategory.PASSWORD,
        raw_value="SuperSecret123!",
        placeholder="[PASSWORD_1]",
        source_node_id=10
    )
    source_node = DOMNode(
        node_id=10,
        tag_name="input",
        element_type="password",
        element_id="pwd_field",
        name="password",
        is_visible=True,
        bounding_box={"x": 100, "y": 100, "width": 200, "height": 40},
        attributes={"type": "password", "placeholder": "Password", "name": "password"}
    )
    token = vault.store_match(match, origin="https://bank.example.com", node=source_node)
    return vault, token, source_node


def test_vault_origin_mismatch_rejection(vault_setup):
    vault, token, source_node = vault_setup
    
    # Attempt restoration on a different origin (e.g. attacker domain)
    with pytest.raises(VaultRestorationError) as exc_info:
        vault.restore(token, target_node=source_node, current_origin="https://evil-attacker.com")
    
    assert "Origin mismatch" in str(exc_info.value)


def test_vault_fingerprint_mismatch_rejection(vault_setup):
    """
    Same origin, same numeric node_id, BUT different node properties → different fingerprint.
    This is the out-of-DOM identity check: even if an attacker reuses node_id 10,
    the Python-side fingerprint won't match.
    """
    vault, token, source_node = vault_setup
    
    # Attacker node has same node_id but different name/element_id
    spoofed_node = DOMNode(
        node_id=10,
        tag_name="input",
        element_type="password",
        element_id="attacker_injected_field",
        name="password",
        is_visible=True,
        bounding_box={"x": 100, "y": 100, "width": 200, "height": 40},
        attributes={"type": "password", "placeholder": "Password", "name": "password"}
    )
    
    with pytest.raises(VaultRestorationError) as exc_info:
        vault.restore(token, target_node=spoofed_node, current_origin="https://bank.example.com")
    
    assert "fingerprint does not match" in str(exc_info.value)


def test_vault_non_password_type_rejection():
    """
    Store a password token into a password field, then try to restore into a text field.
    This tests that even if fingerprint check is somehow bypassed (backward compat path),
    the element_type check still catches password→text injection.
    
    We store WITHOUT a node (so no fingerprint is registered) to specifically
    test the type-check layer independently.
    """
    vault = ClientVault()
    match = PIIMatch(
        category=PIICategory.PASSWORD,
        raw_value="SuperSecret123!",
        placeholder="[PASSWORD_1]",
        source_node_id=10
    )
    # Store without node → no fingerprint registered → tests downstream checks
    vault.store_match(match, origin="https://bank.example.com", node=None)
    
    text_node = DOMNode(
        node_id=10,
        tag_name="input",
        element_type="text",
        element_id="pwd_field",
        name="password",
        is_visible=True,
        bounding_box={"x": 100, "y": 100, "width": 200, "height": 40},
        attributes={"type": "text"}
    )
    
    with pytest.raises(VaultRestorationError) as exc_info:
        vault.restore("[PASSWORD_1]", target_node=text_node, current_origin="https://bank.example.com")
    
    assert "Password secrets can only be restored into input type='password'" in str(exc_info.value)


def test_vault_opacity_zero_exfiltration_rejection(vault_setup):
    """
    Restore with the SAME node (fingerprint matches) but opacity=0.
    Tests that the visibility check catches transparent exfiltration.
    """
    vault, token, source_node = vault_setup
    
    # Use exact same node but set opacity to 0 in attributes
    transparent_node = DOMNode(
        node_id=source_node.node_id,
        tag_name=source_node.tag_name,
        element_type=source_node.element_type,
        element_id=source_node.element_id,
        name=source_node.name,
        is_visible=True,  # DOM says visible, but opacity says hidden
        bounding_box={"x": 100, "y": 100, "width": 200, "height": 40},
        attributes={"type": "password", "placeholder": "Password", "name": "password", "opacity": "0"}
    )
    
    with pytest.raises(VaultRestorationError) as exc_info:
        vault.restore(token, target_node=transparent_node, current_origin="https://bank.example.com")
    
    assert "transparent or hidden DOM node" in str(exc_info.value)


def test_vault_1px_exfiltration_rejection(vault_setup):
    """
    Restore with the SAME node (fingerprint matches) but 1x1 bounding box.
    Tests that the size check catches tiny-element exfiltration.
    """
    vault, token, source_node = vault_setup
    
    tiny_node = DOMNode(
        node_id=source_node.node_id,
        tag_name=source_node.tag_name,
        element_type=source_node.element_type,
        element_id=source_node.element_id,
        name=source_node.name,
        is_visible=True,
        bounding_box={"x": 100, "y": 100, "width": 1, "height": 1},
        attributes={"type": "password", "placeholder": "Password", "name": "password"}
    )
    
    with pytest.raises(VaultRestorationError) as exc_info:
        vault.restore(token, target_node=tiny_node, current_origin="https://bank.example.com")
    
    assert "1px or zero-size exfiltration DOM node" in str(exc_info.value)


def test_vault_valid_restoration_success(vault_setup):
    vault, token, source_node = vault_setup
    
    secret = vault.restore(token, target_node=source_node, current_origin="https://bank.example.com")
    assert secret == "SuperSecret123!"


def test_vault_fingerprint_not_spoofable_via_dom():
    """
    Core security property: the fingerprint is computed server-side from node properties,
    NOT from any DOM attribute the page can set. Even if a malicious page sets
    data-webveil-id to the exact right value, it doesn't affect the fingerprint.
    """
    vault = ClientVault()
    
    real_node = DOMNode(
        node_id=5, tag_name="input", element_type="text",
        element_id="real_field", name="email",
        is_visible=True, bounding_box={"x": 10, "y": 10, "width": 200, "height": 30},
        attributes={"type": "text", "name": "email"}
    )
    match = PIIMatch(
        category=PIICategory.EMAIL,
        raw_value="user@example.com",
        placeholder="[EMAIL_1]",
        source_node_id=5
    )
    vault.store_match(match, origin="https://legit.com", node=real_node)
    
    # Attacker creates node with DIFFERENT element_id but same node_id
    attacker_node = DOMNode(
        node_id=5, tag_name="input", element_type="text",
        element_id="attacker_field", name="email",
        is_visible=True, bounding_box={"x": 10, "y": 10, "width": 200, "height": 30},
        attributes={"type": "text", "name": "email", "data-webveil-id": "anything-the-page-sets"}
    )
    
    with pytest.raises(VaultRestorationError):
        vault.restore("[EMAIL_1]", target_node=attacker_node, current_origin="https://legit.com")


def test_vault_clear_wipes_fingerprints():
    """Clearing the vault must also wipe the fingerprint registry."""
    vault = ClientVault()
    node = DOMNode(
        node_id=1, tag_name="input", element_type="text",
        element_id="f1", name="name",
        is_visible=True, bounding_box={"x": 10, "y": 10, "width": 200, "height": 30},
        attributes={"type": "text"}
    )
    match = PIIMatch(
        category=PIICategory.NAME,
        raw_value="John Doe",
        placeholder="[NAME_1]",
        source_node_id=1
    )
    vault.store_match(match, origin="https://test.com", node=node)
    
    assert len(vault._node_fingerprints) == 1
    vault.clear()
    assert len(vault._node_fingerprints) == 0
    assert len(vault._entries) == 0
