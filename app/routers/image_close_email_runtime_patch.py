from . import case_event_policy_patch, image_evidence_patch

# image_evidence_patch imported close_ticket directly when the module was loaded.
# Rebind that local reference to the milestone policy wrapper so image-report
# closures send the final case email with the generated PDFs and embedded photos.
image_evidence_patch.close_ticket = case_event_policy_patch._policy_close_ticket
