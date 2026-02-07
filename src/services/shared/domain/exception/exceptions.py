class DomainException(Exception):
    """ドメイン層で発生する基底例外"""

    pass


class ResourceNotFoundException(DomainException):
    """リソースが見つからない場合"""

    pass


class BusinessRuleViolationException(DomainException):
    """ビジネスルールに違反した場合"""

    pass


class DuplicateResourceException(DomainException):
    """リソースの重複エラー（条件付き書き込みの失敗時）"""

    pass
