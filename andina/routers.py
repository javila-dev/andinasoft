
class sandville_router():
    def db_for_read(self,model,**hints):
        if model._meta.app_label=='sandville':
            return 'sandville'
        return None
    def db_for_write(self,model,**hints):
        if model._meta.app_label=='sandville':
            return 'sandville'
        return None
    def allow_relation(self,obj1,obj2,**hints):
        db_list=('sandville')
        if obj1._meta.app_label == 'sandville' or \
            obj2._meta.app_label == 'sandville':
            return True
        return None
    def allow_migratate(self,db,app_label,model_name=None,**hints):
        if app_label == 'sandville':
            return db == 'sandville'
        return None

class venecia_router():
    def db_for_read(self,model,**hints):
        if model._meta.app_label=='venecia':
            return 'venecia'
        return None
    def db_for_write(self,model,**hints):
        if model._meta.app_label=='venecia':
            return 'venecia'
        return None
    def allow_relation(self,obj1,obj2,**hints):
        db_list=('venecia')
        if obj1._meta.app_label == 'venecia' or \
            obj2._meta.app_label == 'venecia':
            return True
        return None
    def allow_migratate(self,db,app_label,model_name=None,**hints):
        if app_label == 'venecia':
            return db == 'venecia'
        return None