"""
text_presentation_instances.py
"""

population = [
    # Frame OS Engineer, default
    # Large
    {'Asset': 'Open title large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
     'Text style': 'Corner Title Large'},
    {'Asset': 'Open copyright notice large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
     'Text style': 'boilerplate'},
    {'Asset': 'Block title large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
     'Text style': 'Block Title Large'},
    {'Asset': 'Block body large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
     'Text style': 'Block Body Large'},

    # # Medium
    # {'Asset': 'Open title medium', 'Presentation': 'default', 'Drawing type': 'OS Engineer medium',
    #  'Text style': 'Corner Title Large'},
    # {'Asset': 'Open copyright notice large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'boilerplate'},
    # {'Asset': 'Block title large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'Block title Large'},
    # {'Asset': 'Block body large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'Block Body Large'},
    #
    # # Small
    # {'Asset': 'Open title large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'Corner Title Large'},
    # {'Asset': 'Open copyright notice large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'boilerplate'},
    # {'Asset': 'Block title large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'Block title Large'},
    # {'Asset': 'Block body large', 'Presentation': 'default', 'Drawing type': 'OS Engineer large',
    #  'Text style': 'Block Body Large'},

    # Starr class diagram, default
    {'Asset': 'label', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'binary association name', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'generalization name', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'class mult name', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'see also', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9italic'},
    {'Asset': 'class name', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p12title'},
    {'Asset': 'attributes', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'methods', 'Presentation': 'default', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},

    # Starr class diagram, diagnostic
    {'Asset': 'label', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'binary association name', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'generalization name', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'class mult name', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'see also', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9italic'},
    {'Asset': 'class name', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p12title'},
    {'Asset': 'attributes', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},
    {'Asset': 'methods', 'Presentation': 'diagnostic', 'Drawing type': 'Starr class diagram', 'Text style': 'p9body'},

    # xUML class diagram, default
    {'Asset': 'label', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},
    {'Asset': 'binary association name', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},
    {'Asset': 'generalization name', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},
    {'Asset': 'class mult name', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},
    {'Asset': 'see also', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9italic'},
    {'Asset': 'class name', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p12title'},
    {'Asset': 'attributes', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},
    {'Asset': 'methods', 'Presentation': 'default', 'Drawing type': 'xUML class diagram', 'Text style': 'p9body'},

    # Shlaer-Mellor class diagram, default
    {'Asset': 'label', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},
    {'Asset': 'binary association name', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},
    {'Asset': 'generalization name', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},
    {'Asset': 'class mult name', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},
    {'Asset': 'see also', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9italic'},
    {'Asset': 'class name', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p12title'},
    {'Asset': 'attributes', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},
    {'Asset': 'methods', 'Presentation': 'default', 'Drawing type': 'Shlaer-Mellor class diagram', 'Text style': 'p9body'},

    {'Asset': 'event', 'Presentation': 'default', 'Drawing type': 'xUML state machine diagram', 'Text style': 'p9body'},
    {'Asset': 'activity', 'Presentation': 'default', 'Drawing type': 'xUML state machine diagram', 'Text style': 'p9body'},
    {'Asset': 'state name', 'Presentation': 'default', 'Drawing type': 'xUML state machine diagram', 'Text style': 'p12title'}
]