"""Pipeline error types. Any of them stops the whole run before publication."""


class PipelineError(Exception):
    """Base class: the run is marked FAILED and nothing is published."""


class InputMissingError(PipelineError):
    """Input folder or the minimum number of input files is missing."""


class BatchRejectedError(PipelineError):
    """A validation rule rejected one input file; the whole batch stops."""

    def __init__(self, rule_id: str, source_file: str, message: str):
        self.rule_id = rule_id
        self.source_file = source_file
        super().__init__(f"[{rule_id}] {source_file}: {message}")


class ExternalSourceError(PipelineError):
    """The external API could not be reached or returned an HTTP error."""


class ExternalDataError(PipelineError):
    """The external response does not meet the expected structure, types, units or coverage."""


class IntegrationError(PipelineError):
    """Join checks failed (duplicate keys, unmatched rows, counts or totals changed)."""


class VerificationError(PipelineError):
    """A published artefact (workbook/report) disagrees with the validated data."""
