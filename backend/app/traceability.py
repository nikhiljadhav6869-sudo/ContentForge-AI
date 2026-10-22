"""Conservative, inspectable evidence matching. Support is not a truth guarantee."""

import re
from sqlalchemy import select, func
from .db import (
    ArtifactVersion,
    ContentArtifact,
    SourcePassage,
    SourceDocument,
    FactualClaim,
    ClaimEvidence,
    PublishingJob,
    now,
)

SUPPORTED = "Battery electric vehicles produce no tailpipe emissions."
DISPUTED = "Electric vehicles are emission-free across their entire lifecycle."
UNVERIFIED = "Every electric vehicle in India travels 900 kilometres on a single charge."


def latest_versions(db, run_id):
    result = []
    for artifact in db.scalars(select(ContentArtifact).where(ContentArtifact.run_id == run_id)).all():
        version = db.scalar(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact.id)
            .order_by(ArtifactVersion.number.desc())
        )
        if version:
            result.append((artifact, version))
    return result


def new_version(db, artifact, body, reason, execution_id=None):
    number = (
        db.scalar(select(func.max(ArtifactVersion.number)).where(ArtifactVersion.artifact_id == artifact.id)) or 0
    ) + 1
    version = ArtifactVersion(
        artifact_id=artifact.id, number=number, body=body, reason=reason, execution_id=execution_id
    )
    db.add(version)
    db.flush()
    # A schedule always points to an explicitly approved immutable version.
    for job in db.scalars(
        select(PublishingJob).where(PublishingJob.artifact_id == artifact.id, PublishingJob.status == "scheduled_draft")
    ):
        job.status = "needs_review"
    return version


def candidates(body):
    matches = []
    for match in re.finditer(r"[^\n.!?]+[.!?]", body):
        text = match.group().strip().lstrip("#*- ")
        if len(text) < 25 or text.endswith("?"):
            continue
        if re.match(
            r"(?i)(consider|compare|ask|explore|learn|check|review|use|start|join|save|share|before|try|what)\b", text
        ):
            continue
        start = body.find(text, match.start(), match.end())
        if start >= 0:
            matches.append((text, start, start + len(text)))
    return matches


def verify_version(db, version, source_ids, execution_id=None, demo=False, edited=False):
    existing = db.scalars(select(FactualClaim).where(FactualClaim.version_id == version.id)).all()
    if existing:
        return existing
    passages = (
        db.scalars(select(SourcePassage).where(SourcePassage.source_id.in_(source_ids))).all() if source_ids else []
    )
    claims = []
    for text, start, end in candidates(version.body):
        links = []
        status = "unverified"
        explanation = "No exact supporting passage was found. Human evidence assessment is required; this is not proof the claim is false."
        if not edited:
            for passage in passages:
                source_sentences = [
                    sentence.strip().casefold() for sentence in re.split(r"(?<=[.!?])\s+|\n+", passage.text)
                ]
                if text.casefold() in source_sentences:
                    links.append((passage, "supports", text))
                elif demo and text == DISPUTED and "not emission-free across their entire lifecycle" in passage.text:
                    quote = "Electric vehicles are not emission-free across their entire lifecycle."
                    links.append((passage, "contradicts", quote))
            if any(relation == "contradicts" for _, relation, _ in links):
                status = "disputed"
                explanation = (
                    "The stored sample passage explicitly contradicts this demo claim. It is flagged for revision."
                )
            elif links:
                status = "supported"
                explanation = "The claim is quoted verbatim in the linked source passage(s). This establishes textual support, not independent factual truth."
                if demo:
                    explanation += " These are labeled demonstration references."
        else:
            explanation = "Human edit invalidated prior verification. This new version requires review; no earlier evidence status has been inherited."
        claim = FactualClaim(
            version_id=version.id,
            execution_id=execution_id,
            text=text,
            start=start,
            end=end,
            status=status,
            explanation=explanation,
            history=[
                {"state": "generated", "at": version.created_at},
                {"state": "extracted", "at": now()},
                {"state": "evidence_collected", "at": now(), "passage_count": len(links)},
                {"state": status, "at": now()},
            ],
        )
        db.add(claim)
        db.flush()
        for passage, relation, quote in links:
            db.add(ClaimEvidence(claim_id=claim.id, passage_id=passage.id, relation=relation, quote=quote))
        claims.append(claim)
    return claims


def evidence_for_run(db, run_id):
    artifacts = db.scalars(select(ContentArtifact).where(ContentArtifact.run_id == run_id)).all()
    ids = [a.id for a in artifacts]
    versions = (
        db.scalars(
            select(ArtifactVersion).where(ArtifactVersion.artifact_id.in_(ids)).order_by(ArtifactVersion.number)
        ).all()
        if ids
        else []
    )
    claims = (
        db.scalars(select(FactualClaim).where(FactualClaim.version_id.in_([v.id for v in versions]))).all()
        if versions
        else []
    )
    links = (
        db.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id.in_([c.id for c in claims]))).all()
        if claims
        else []
    )
    return artifacts, versions, claims, links
