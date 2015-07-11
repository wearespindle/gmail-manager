import factory


class EmailAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'gmailmanager.EmailAccount'
