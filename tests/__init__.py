import warnings

# Suppress upstream Google ADK BaseAgentConfig deprecation warning
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r".*BaseAgentConfig is deprecated.*")
